import asyncio
import logging
import os
from asyncio import CancelledError
from collections import deque
from enum import Enum
from importlib.util import find_spec
from typing import Callable, Deque, Optional, Union

from pandablocks.asyncio import AsyncioClient
from pandablocks.hdf import (
    EndData,
    FrameData,
    StartData,
    create_default_pipeline,
    stop_pipeline,
)
from pandablocks.responses import EndReason, ReadyData
from softioc import alarm, builder
from softioc.pythonSoftIoc import RecordWrapper

from ._pvi import PviGroup, add_automatic_pvi_info, add_data_capture_pvi_info
from ._types import ONAM_STR, ZNAM_STR, EpicsName

HDFReceived = Union[ReadyData, StartData, FrameData, EndData]


class CaptureMode(Enum):
    """
    The mode which the circular buffer will use to flush
    """

    #: Wait till N frames are recieved then write them
    #:  and finish capture
    FIRST_N = 0

    #: On EndData write the last N frames
    LAST_N = 1

    #: Write data as received until Capture set to 0
    FOREVER = 2


class HDF5Buffer:
    _buffer_index = None
    start_data = None
    number_of_received_rows = 0
    finish_capturing = False
    circular_buffer: Deque[FrameData] = deque()
    number_of_rows_in_circular_buffer = 0

    def __init__(
        self,
        capture_mode: CaptureMode,
        filepath: str,
        number_of_rows_to_capture: int,
        status_message_setter: Callable,
        number_received_setter: Callable,
    ):
        # Only one filename - user must stop capture and set new FileName/FilePath
        # for new files

        self.capture_mode = capture_mode
        self.filepath = filepath
        self.number_of_rows_to_capture = number_of_rows_to_capture
        self.status_message_setter = status_message_setter
        self.number_received_setter = number_received_setter

        if (
            self.capture_mode == CaptureMode.LAST_N
            and self.number_of_rows_to_capture <= 0
        ):
            raise RuntimeError("Number of rows to capture must be > 0 on LAST_N mode")

    def put_data_to_file(self, data: HDFReceived):
        try:
            self.pipeline[0].queue.put_nowait(data)
        except Exception as ex:
            logging.exception(f"Failed to save the data to HDF5 file: {ex}")

    def start_pipeline(self):
        self.pipeline = create_default_pipeline(iter([self.filepath]))

    def get_written_data_size(self):
        return min([ds.size for ds in self.pipeline[1].datasets])

    def stop_pipeline(self):
        stop_pipeline(self.pipeline)

    def _handle_StartData(self, data: StartData):
        if self.start_data and data != self.start_data:
            # PandA was disarmed, had config changed, and rearmed.
            # Cannot process to the same file with different start data.
            logging.error(
                "New start data detected, differs from previous start "
                "data for this file. Aborting HDF5 data capture."
            )

            self.status_message_setter(
                "Mismatched StartData packet for file",
                severity=alarm.MAJOR_ALARM,
                alarm=alarm.STATE_ALARM,
            )
            self.put_data_to_file(
                EndData(self.number_of_received_rows, EndReason.START_DATA_MISMATCH)
            )

            self.finish_capturing = True

        if self.start_data is None:
            # Only pass StartData to pipeline if we haven't previously
            # - if we have there will already be an in-progress HDF file
            # that we should just append data to
            self.start_data = data
            self.put_data_to_file(data)

    def _capture_first_n(self, data: FrameData):
        """
        Capture framedata as it comes in. Stop when number of frames exceeds
        number_of_rows_to_capture, and cut off the data so that it's length
        number_of_rows_to_capture.
        """
        self.number_of_received_rows += len(data.data)

        if (
            self.number_of_rows_to_capture > 0
            and self.number_of_received_rows > self.number_of_rows_to_capture
        ):
            # Discard extra collected data points if necessary
            data.data = data.data[
                : self.number_of_rows_to_capture - self.number_of_received_rows
            ].copy()
            self.number_of_received_rows = self.number_of_rows_to_capture

        self.put_data_to_file(data)
        self.number_received_setter(self.number_of_received_rows)

        if (
            self.number_of_rows_to_capture > 0
            and self.number_of_received_rows == self.number_of_rows_to_capture
        ):
            # Reached configured capture limit, stop the file
            logging.info(
                f"Requested number of frames ({self.number_of_rows_to_capture}) "
                "captured, disabling Capture."
            )
            self.status_message_setter("Requested number of frames captured")
            self.put_data_to_file(EndData(self.number_of_received_rows, EndReason.OK))
            self.finish_capturing = True

    def _capture_forever(self, data: FrameData):
        self.put_data_to_file(data)
        self.number_of_received_rows += len(data.data)
        self.number_received_setter(self.number_of_received_rows)

    def _capture_last_n(self, data: FrameData):
        """
        Append every FrameData to a buffer until the number of rows equals
        `:NumCapture`. Then rewrite the data circularly.

        Only write the data once PCAP is received.
        """
        self.circular_buffer.append(data)
        self.number_of_received_rows += len(data.data)
        self.number_of_rows_in_circular_buffer += len(data.data)

        if self.number_of_rows_in_circular_buffer > self.number_of_rows_to_capture:
            self.status_message_setter(
                "NumCapture received, rewriting first frames received"
            )

        else:
            self.status_message_setter("Filling buffer to NumReceived")

        while self.number_of_rows_in_circular_buffer > self.number_of_rows_to_capture:
            first_frame_data = self.circular_buffer.popleft()
            first_frame_data_length = len(first_frame_data.data)

            if first_frame_data_length >= self.number_of_rows_to_capture:
                # More data than we want to capture, all in a single FrameData
                # We can just slice with the NumCapture since this has to be the
                # only FrameData in the buffer at this point
                assert len(self.circular_buffer) == 0
                first_frame_data.data = first_frame_data.data[
                    -self.number_of_rows_to_capture :
                ].copy()
                self.circular_buffer.appendleft(first_frame_data)
                self.number_of_rows_in_circular_buffer = self.number_of_rows_to_capture
            elif (
                first_frame_data_length
                > self.number_of_rows_in_circular_buffer
                - self.number_of_rows_to_capture
            ):
                # We can slice from the beginning of the FrameData to have the desired
                # number of rows
                indices_to_discard = (
                    self.number_of_rows_in_circular_buffer
                    - self.number_of_rows_to_capture
                )
                first_frame_data.data = first_frame_data.data[
                    indices_to_discard:
                ].copy()
                self.circular_buffer.appendleft(first_frame_data)
                self.number_of_rows_in_circular_buffer -= indices_to_discard
                assert (
                    self.number_of_rows_in_circular_buffer
                    == self.number_of_rows_to_capture
                )
            else:
                # If we remove the enire first frame data then the buffer will still
                # be too big, or it will be exactly the number of rows we want
                self.number_of_rows_in_circular_buffer -= first_frame_data_length

        self.number_received_setter(self.number_of_received_rows)

    def _handle_FrameData(self, data: FrameData):
        match self.capture_mode:
            case CaptureMode.FIRST_N:
                self._capture_first_n(data)
            case CaptureMode.LAST_N:
                self._capture_last_n(data)
            case CaptureMode.FOREVER:
                self._capture_forever(data)

    def _handle_EndData(self, data: EndData):
        if self.capture_mode == CaptureMode.LAST_N:
            # Put all the data to file
            self.status_message_setter(
                "Finishing capture, writing buffered frames to file"
            )
            # In LAST_N only write FrameData if the EndReason is OK
            if data.reason == EndReason.OK:
                for frame_data in self.circular_buffer:
                    self.put_data_to_file(frame_data)

        if self.capture_mode == CaptureMode.FOREVER:
            self.start_data = None
            self.status_message_setter("Finished capture, waiting for next ReadyData")
        else:
            self.finish_capturing = True
            self.status_message_setter("Finished capture")

        self.put_data_to_file(data)

    def handle_data(self, data: HDFReceived):
        match data:
            case ReadyData():
                self.status_message_setter("Starting capture")
            case StartData():
                self._handle_StartData(data)
            case FrameData():
                self._handle_FrameData(data)
            case EndData():
                self._handle_EndData(data)
            case _:
                raise RuntimeError(
                    f"Data was recieved that was of type {type(data)}, not"
                    "StartData, EndData, ReadyData or FrameData"
                )


class HDF5RecordController:
    """Class to create and control the records that handle HDF5 processing"""

    _DATA_PREFIX = "DATA"

    _client: AsyncioClient

    _directory_record: RecordWrapper
    _file_name_record: RecordWrapper
    _file_number_record: RecordWrapper
    _file_format_record: RecordWrapper
    _num_capture_record: RecordWrapper
    _flush_period_record: RecordWrapper
    _capture_control_record: RecordWrapper  # Turn capture on/off
    _status_message_record: RecordWrapper  # Reports status and error messages

    _handle_hdf5_data_task: Optional[asyncio.Task] = None

    def __init__(self, client: AsyncioClient, record_prefix: str):
        if find_spec("h5py") is None:
            logging.warning("No HDF5 support detected - skipping creating HDF5 records")
            return

        self._client = client

        path_length = os.pathconf("/", "PC_PATH_MAX")
        filename_length = os.pathconf("/", "PC_NAME_MAX")

        # Create the records, including an uppercase alias for each
        # Naming convention and settings (mostly) copied from FSCN2 HDF5 records
        directory_record_name = EpicsName(self._DATA_PREFIX + ":HDFDirectory")
        self._directory_record = builder.longStringOut(
            directory_record_name,
            length=path_length,
            DESC="File path for HDF5 files",
            validate=self._parameter_validate,
            on_update=self._update_full_file_path,
        )
        add_automatic_pvi_info(
            PviGroup.HDF,
            self._directory_record,
            directory_record_name,
            builder.longStringOut,
        )
        self._directory_record.add_alias(
            record_prefix + ":" + directory_record_name.upper()
        )

        file_name_record_name = EpicsName(self._DATA_PREFIX + ":HDFFileName")
        self._file_name_record = builder.longStringOut(
            file_name_record_name,
            length=filename_length,
            DESC="File name prefix for HDF5 files",
            validate=self._parameter_validate,
            on_update=self._update_full_file_path,
        )
        add_automatic_pvi_info(
            PviGroup.HDF,
            self._file_name_record,
            file_name_record_name,
            builder.longStringOut,
        )
        self._file_name_record.add_alias(
            record_prefix + ":" + file_name_record_name.upper()
        )

        full_file_path_record_name = EpicsName(self._DATA_PREFIX + ":HDFFullFilePath")
        self._full_file_path_record = builder.longStringIn(
            full_file_path_record_name,
            length=path_length + 1 + filename_length,
            DESC="Full HDF5 file name with directory",
        )
        add_automatic_pvi_info(
            PviGroup.HDF,
            self._full_file_path_record,
            full_file_path_record_name,
            builder.longStringIn,
        )
        self._file_name_record.add_alias(
            record_prefix + ":" + full_file_path_record_name.upper()
        )

        num_capture_record_name = EpicsName(self._DATA_PREFIX + ":NumCapture")
        self._num_capture_record = builder.longOut(
            num_capture_record_name,
            initial_value=0,  # Infinite capture
            DESC="Number of frames to capture. 0=infinite",
            DRVL=0,
        )

        add_automatic_pvi_info(
            PviGroup.CAPTURE,
            self._num_capture_record,
            num_capture_record_name,
            builder.longOut,
        )
        # No validate - users are allowed to change this at any time
        self._num_capture_record.add_alias(
            record_prefix + ":" + num_capture_record_name.upper()
        )

        num_received_record_name = EpicsName(self._DATA_PREFIX + ":NumReceived")
        self._num_received_record = builder.longIn(
            num_received_record_name,
            initial_value=0,
            DESC="Number of frames written to HDF file.",
        )

        add_automatic_pvi_info(
            PviGroup.CAPTURE,
            self._num_received_record,
            num_received_record_name,
            builder.longIn,
        )
        self._num_received_record.add_alias(
            record_prefix + ":" + num_received_record_name.upper()
        )

        flush_period_record_name = EpicsName(self._DATA_PREFIX + ":FlushPeriod")
        self._flush_period_record = builder.aOut(
            flush_period_record_name,
            initial_value=1.0,
            DESC="Frequency that data is flushed (seconds)",
            EGU="s",
        )
        add_automatic_pvi_info(
            PviGroup.CAPTURE,
            self._flush_period_record,
            flush_period_record_name,
            builder.aOut,
        )
        self._flush_period_record.add_alias(
            record_prefix + ":" + flush_period_record_name.upper()
        )

        capture_control_record_name = EpicsName(self._DATA_PREFIX + ":Capture")
        self._capture_control_record = builder.boolOut(
            capture_control_record_name,
            ZNAM=ZNAM_STR,
            ONAM=ONAM_STR,
            on_update=self._capture_on_update,
            validate=self._capture_validate,
            DESC="Start/stop HDF5 capture",
        )
        add_data_capture_pvi_info(
            PviGroup.CAPTURE,
            capture_control_record_name,
            self._capture_control_record,
        )
        self._capture_control_record.add_alias(
            record_prefix + ":" + capture_control_record_name.upper()
        )

        capture_mode_record_name = EpicsName(self._DATA_PREFIX + ":CaptureMode")
        self._capture_mode_record = builder.mbbOut(
            capture_mode_record_name,
            *[capture_mode.name for capture_mode in CaptureMode],
            initial_value=0,
            DESC="Choose how to hdf writer flushes",
        )
        add_automatic_pvi_info(
            PviGroup.CAPTURE,
            self._capture_mode_record,
            capture_mode_record_name,
            builder.mbbOut,
        )
        self._capture_mode_record.add_alias(
            record_prefix + ":" + capture_mode_record_name.upper()
        )

        status_message_record_name = EpicsName(self._DATA_PREFIX + ":Status")
        self._status_message_record = builder.longStringIn(
            status_message_record_name,
            initial_value="OK",
            length=200,
            DESC="Reports current status of HDF5 capture",
        )
        add_automatic_pvi_info(
            PviGroup.OUTPUTS,
            self._status_message_record,
            status_message_record_name,
            builder.stringIn,
        )
        self._status_message_record.add_alias(
            record_prefix + ":" + status_message_record_name.upper()
        )

    def _parameter_validate(self, record: RecordWrapper, new_val) -> bool:
        """Control when values can be written to parameter records
        (file name etc.) based on capturing record's value"""
        logging.debug(f"Validating record {record.name} value {new_val}")
        if self._capture_control_record.get():
            # Currently capturing, discard parameter updates
            logging.warning(
                "Data capture in progress. Update of HDF5 "
                f"record {record.name} with new value {new_val} discarded."
            )
            return False
        return True

    async def _update_full_file_path(self, new_val) -> None:
        self._full_file_path_record.set(self._get_filepath())

    async def _handle_hdf5_data(self) -> None:
        """Handles writing HDF5 data from the PandA to file, based on configuration
        in the various HDF5 records.
        This method expects to be run as an asyncio Task."""
        try:
            # Set up the hdf buffer
            num_capture: int = self._num_capture_record.get()
            capture_mode: CaptureMode = CaptureMode(self._capture_mode_record.get())
            filepath = self._get_filepath()
            buffer = HDF5Buffer(
                capture_mode,
                filepath,
                num_capture,
                self._status_message_record.set,
                self._num_received_record.set,
            )
            buffer.start_pipeline()

            flush_period: float = self._flush_period_record.get()
            async for data in self._client.data(
                scaled=False, flush_period=flush_period
            ):
                logging.debug(f"Received data packet: {data}")

                buffer.handle_data(data)
                if buffer.finish_capturing:
                    break

        except CancelledError:
            logging.info("Capturing task cancelled, closing HDF5 file")
            self._status_message_record.set("Capturing disabled")
            # Only send EndData if we know the file was opened - could be cancelled
            # before PandA has actually send any data
            if buffer.start_data:
                buffer.put_data_to_file(
                    EndData(buffer.number_of_received_rows, EndReason.OK)
                )

        except Exception:
            logging.exception("HDF5 data capture terminated due to unexpected error")
            self._status_message_record.set(
                "Capture disabled, unexpected exception",
                severity=alarm.MAJOR_ALARM,
                alarm=alarm.STATE_ALARM,
            )
            # Only send EndData if we know the file was opened - exception could happen
            # before file was opened
            if buffer.start_data:
                buffer.put_data_to_file(
                    EndData(buffer.number_of_received_rows, EndReason.UNKNOWN_EXCEPTION)
                )

        finally:
            logging.debug("Finishing processing HDF5 PandA data")
            buffer.stop_pipeline()
            self._num_received_record.set(buffer.number_of_received_rows)
            self._capture_control_record.set(0)

    def _get_filepath(self) -> str:
        """Create the file path for the HDF5 file from the relevant records"""
        return "/".join(
            (
                self._directory_record.get(),
                self._file_name_record.get(),
            )
        )

    async def _capture_on_update(self, new_val: int) -> None:
        """Process an update to the Capture record, to start/stop recording HDF5 data"""
        logging.debug(f"Entering HDF5:Capture record on_update method, value {new_val}")
        if new_val:
            if self._handle_hdf5_data_task:
                logging.warning("Existing HDF5 capture running, cancelling it.")
                self._handle_hdf5_data_task.cancel()

            self._handle_hdf5_data_task = asyncio.create_task(self._handle_hdf5_data())
        else:
            assert self._handle_hdf5_data_task
            self._handle_hdf5_data_task.cancel()  # Abort any HDF5 file writing
            self._handle_hdf5_data_task = None

    def _capture_validate(self, record: RecordWrapper, new_val: int) -> bool:
        """Check the required records have been set before allowing Capture=1"""
        if new_val:
            try:
                self._get_filepath()
            except ValueError:
                logging.exception("At least 1 required record had no value")
                return False
            except Exception:
                logging.exception("Unexpected exception creating file name")
                return False

        return True
