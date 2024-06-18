import asyncio
import logging
import os
from asyncio import CancelledError
from collections import deque
from dataclasses import dataclass
from enum import Enum
from importlib.util import find_spec
from pathlib import Path
from typing import Callable, Deque, Dict, Optional, Union

from pandablocks.asyncio import AsyncioClient
from pandablocks.hdf import (
    EndData,
    FrameData,
    Pipeline,
    StartData,
    create_default_pipeline,
    stop_pipeline,
)
from pandablocks.responses import EndReason, ReadyData
from softioc import alarm, builder
from softioc.pythonSoftIoc import RecordWrapper

from ._pvi import PviGroup, add_automatic_pvi_info, add_data_capture_pvi_info
from ._tables import ReadOnlyPvaTable
from ._types import ONAM_STR, ZNAM_STR, EpicsName, epics_to_panda_name

HDFReceived = Union[ReadyData, StartData, FrameData, EndData]


class CaptureMode(Enum):
    """
    The mode which the circular buffer will use to flush.
    """

    #: Wait till N frames are recieved then write them
    #:  and finish capture
    FIRST_N = 0

    #: On EndData write the last N frames
    LAST_N = 1

    #: Write data as received until Capture set to 0
    FOREVER = 2


class NumCapturedSetter(Pipeline):
    def __init__(self, number_captured_setter: Callable) -> None:
        self.number_captured_setter = number_captured_setter
        self.number_captured_setter(0)
        super().__init__()

        self.what_to_do = {int: self.set_record}

    def set_record(self, value: int):
        self.number_captured_setter(value)


class HDF5Buffer:
    _buffer_index = None
    start_data = None
    number_of_received_rows = 0
    finish_capturing = False
    number_of_rows_in_circular_buffer = 0

    def __init__(
        self,
        capture_mode: CaptureMode,
        filepath: str,
        number_of_rows_to_capture: int,
        status_message_setter: Callable,
        number_received_setter: Callable,
        number_captured_setter_pipeline: NumCapturedSetter,
        dataset_name_cache: Dict[str, Dict[str, str]],
    ):
        # Only one filename - user must stop capture and set new FileName/FilePath
        # for new files

        self.circular_buffer: Deque[FrameData] = deque()
        self.capture_mode = capture_mode

        match capture_mode:
            case CaptureMode.FIRST_N:
                self._handle_FrameData = self._capture_first_n
            case CaptureMode.LAST_N:
                self._handle_FrameData = self._capture_last_n
            case CaptureMode.FOREVER:
                self._handle_FrameData = self._capture_forever
            case _:
                raise RuntimeError("Invalid capture mode")

        self.filepath = filepath
        self.number_of_rows_to_capture = number_of_rows_to_capture
        self.status_message_setter = status_message_setter
        self.number_received_setter = number_received_setter
        self.number_captured_setter_pipeline = number_captured_setter_pipeline
        self.number_captured_setter_pipeline.number_captured_setter(0)

        self.dataset_name_cache = dataset_name_cache

        if (
            self.capture_mode == CaptureMode.LAST_N
            and self.number_of_rows_to_capture <= 0
        ):
            raise RuntimeError("Number of rows to capture must be > 0 on LAST_N mode")

        self.start_pipeline()

    def __del__(self):
        if self.pipeline[0].is_alive():
            stop_pipeline(self.pipeline)

    def put_data_to_file(self, data: HDFReceived):
        try:
            self.pipeline[0].queue.put_nowait(data)
        except Exception as ex:
            logging.exception(f"Failed to save the data to HDF5 file: {ex}")

    def start_pipeline(self):
        self.pipeline = create_default_pipeline(
            iter([self.filepath]),
            self.dataset_name_cache,
            self.number_captured_setter_pipeline,
        )

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

        # Only pass StartData to pipeline if we haven't previously
        else:
            # In LAST_N mode, wait till the end of capture to write
            # the StartData to file.
            # In FOREVER mode write the StartData to file if it's the first received.
            if (
                self.capture_mode == CaptureMode.FIRST_N
                or self.capture_mode == CaptureMode.FOREVER
                and not self.start_data
            ):
                self.put_data_to_file(data)

            self.start_data = data

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

            if first_frame_data_length > self.number_of_rows_to_capture:
                # More data than we want to capture, all in a single FrameData
                # We can just slice with the NumCapture since this has to be the
                # only FrameData in the buffer at this point
                assert len(self.circular_buffer) == 0
                shrinked_data = first_frame_data.data[
                    -self.number_of_rows_to_capture :
                ].copy()
                first_frame_data.data = shrinked_data
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
                shrinked_data = first_frame_data.data[indices_to_discard:].copy()
                first_frame_data.data = shrinked_data
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

    def _handle_EndData(self, data: EndData):
        match self.capture_mode:
            case CaptureMode.LAST_N:
                # In LAST_N only write FrameData if the EndReason is OK
                if data.reason not in (EndReason.OK, EndReason.MANUALLY_STOPPED):
                    self.status_message_setter(
                        f"Stopped capturing with reason {data.reason}, "
                        "skipping writing of buffered frames"
                    )
                    self.finish_capturing = True
                    return

                self.status_message_setter(
                    "Finishing capture, writing buffered frames to file"
                )
                self.put_data_to_file(self.start_data)
                for frame_data in self.circular_buffer:
                    self.put_data_to_file(frame_data)

            case CaptureMode.FOREVER:
                if data.reason != EndReason.MANUALLY_STOPPED:
                    self.status_message_setter(
                        "Finished capture, waiting for next ReadyData"
                    )
                    return

            case CaptureMode.FIRST_N:
                pass  # Frames will have already been written in FirstN

            case _:
                raise RuntimeError("Unknown capture mode")

        self.status_message_setter("Finished capture")
        self.finish_capturing = True
        self.put_data_to_file(data)

    def handle_data(self, data: HDFReceived):
        match data:
            case ReadyData():
                pass
            case StartData():
                self.status_message_setter("Starting capture")
                self._handle_StartData(data)
            case FrameData():
                self._handle_FrameData(data)
            case EndData():
                self._handle_EndData(data)
            case _:
                raise RuntimeError(
                    f"Data was recieved that was of type {type(data)}, not"
                    "StartData, EndData, ReadyData, or FrameData"
                )


@dataclass
class Dataset:
    """A dataset name and capture mode"""

    name: str
    capture: str


class DatasetNameCache:
    """Used for outputing formatted dataset names in the HDF5 writer, and creating
    and updating the HDF5 `DATASETS` table record."""

    def __init__(
        self, datasets: Dict[EpicsName, Dataset], datasets_record_name: EpicsName
    ):
        self._datasets = datasets

        self._datasets_table_record = ReadOnlyPvaTable(
            datasets_record_name, ["Name", "Type"]
        )
        self._datasets_table_record.set_rows(
            ["Name", "Type"], [[], []], length=300, default_data_type=str
        )

    def hdf_writer_names(self):
        """Formats the current dataset names for use in the HDFWriter"""

        hdf_names: Dict[str, Dict[str, str]] = {}
        for record_name, dataset in self._datasets.items():
            if not dataset.name or dataset.capture == "No":
                continue

            field_name = epics_to_panda_name(record_name)

            hdf_names[field_name] = hdf_name = {}

            hdf_name[dataset.capture.split(" ")[-1]] = dataset.name
            # Suffix -min and -max if both are present
            if "Min Max" in dataset.capture:
                hdf_name["Min"] = f"{dataset.name}-min"
                hdf_name["Max"] = f"{dataset.name}-max"
        return hdf_names

    def update_datasets_record(self):
        dataset_name_list = [
            dataset.name
            for dataset in self._datasets.values()
            if dataset.name and dataset.capture != "No"
        ]
        self._datasets_table_record.update_row("Name", dataset_name_list)
        self._datasets_table_record.update_row(
            "Type",
            ["float64"] * len(dataset_name_list),
        )


class HDF5RecordController:
    """Class to create and control the records that handle HDF5 processing"""

    DATA_PREFIX = "DATA"

    _client: AsyncioClient

    _directory_record: RecordWrapper
    _create_directory_record: RecordWrapper
    _directory_exists_record: RecordWrapper
    _file_name_record: RecordWrapper
    _file_number_record: RecordWrapper
    _file_format_record: RecordWrapper
    _num_capture_record: RecordWrapper
    _num_captured_record: RecordWrapper
    _flush_period_record: RecordWrapper
    _capture_control_record: RecordWrapper  # Turn capture on/off
    _status_message_record: RecordWrapper  # Reports status and error messages

    _handle_hdf5_data_task: Optional[asyncio.Task] = None

    def __init__(
        self,
        client: AsyncioClient,
        dataset_cache: Dict[EpicsName, Dataset],
        record_prefix: str,
    ):
        if find_spec("h5py") is None:
            logging.warning("No HDF5 support detected - skipping creating HDF5 records")
            return

        self._client = client
        _datasets_record_name = EpicsName(
            HDF5RecordController.DATA_PREFIX + ":DATASETS"
        )
        self._datasets = DatasetNameCache(dataset_cache, _datasets_record_name)

        path_length = os.pathconf("/", "PC_PATH_MAX")
        filename_length = os.pathconf("/", "PC_NAME_MAX")

        # Create the records, including an uppercase alias for each
        # Naming convention and settings (mostly) copied from FSCN2 HDF5 records
        directory_record_name = EpicsName(self.DATA_PREFIX + ":HDF_DIRECTORY")
        self._directory_record = builder.longStringOut(
            directory_record_name,
            length=path_length,
            DESC="File path for HDF5 files",
            validate=self._parameter_validate,
            on_update=self._update_directory_path,
            always_update=True,
        )
        add_automatic_pvi_info(
            PviGroup.HDF,
            self._directory_record,
            directory_record_name,
            builder.longStringOut,
        )
        self._directory_record.add_alias(
            record_prefix + ":" + self.DATA_PREFIX + ":HDFDirectory"
        )

        create_directory_record_name = EpicsName(self.DATA_PREFIX + ":CreateDirectory")
        self._create_directory_record = builder.longOut(
            create_directory_record_name,
            initial_value=0,
            DESC="Directory creation depth",
        )
        add_automatic_pvi_info(
            PviGroup.HDF,
            self._create_directory_record,
            create_directory_record_name,
            builder.longOut,
        )
        self._create_directory_record.add_alias(
            record_prefix + ":" + create_directory_record_name.upper()
        )

        directory_exists_name = EpicsName(self.DATA_PREFIX + ":DirectoryExists")
        self._directory_exists_record = builder.boolIn(
            directory_exists_name,
            ZNAM="No",
            ONAM="Yes",
            initial_value=0,
            DESC="Directory exists",
        )
        add_automatic_pvi_info(
            PviGroup.HDF,
            self._directory_exists_record,
            directory_exists_name,
            builder.boolIn,
        )
        self._directory_exists_record.add_alias(
            record_prefix + ":" + directory_exists_name.upper()
        )

        file_name_record_name = EpicsName(self.DATA_PREFIX + ":HDF_FILE_NAME")
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
            record_prefix + ":" + self.DATA_PREFIX + ":HDFFileName"
        )

        full_file_path_record_name = EpicsName(self.DATA_PREFIX + ":HDF_FULL_FILE_PATH")
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
        self._full_file_path_record.add_alias(
            record_prefix + ":" + self.DATA_PREFIX + ":HDFFullFilePath"
        )

        num_capture_record_name = EpicsName(self.DATA_PREFIX + ":NUM_CAPTURE")
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
            record_prefix + ":" + self.DATA_PREFIX + ":NumCapture"
        )

        num_captured_record_name = EpicsName(self.DATA_PREFIX + ":NUM_CAPTURED")
        self._num_captured_record = builder.longIn(
            num_captured_record_name,
            initial_value=0,
            DESC="Number of frames written to file.",
        )

        add_automatic_pvi_info(
            PviGroup.CAPTURE,
            self._num_captured_record,
            num_captured_record_name,
            builder.longIn,
        )
        self._num_captured_record.add_alias(
            record_prefix + ":" + self.DATA_PREFIX + ":NumCaptured"
        )

        num_received_record_name = EpicsName(self.DATA_PREFIX + ":NUM_RECEIVED")
        self._num_received_record = builder.longIn(
            num_received_record_name,
            initial_value=0,
            DESC="Number of frames received from panda.",
        )

        add_automatic_pvi_info(
            PviGroup.CAPTURE,
            self._num_received_record,
            num_received_record_name,
            builder.longIn,
        )
        self._num_received_record.add_alias(
            record_prefix + ":" + self.DATA_PREFIX + ":NumReceived"
        )

        flush_period_record_name = EpicsName(self.DATA_PREFIX + ":FLUSH_PERIOD")
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
            record_prefix + ":" + self.DATA_PREFIX + ":FlushPeriod"
        )

        capture_control_record_name = EpicsName(self.DATA_PREFIX + ":CAPTURE")
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
            record_prefix + ":" + self.DATA_PREFIX + ":Capture"
        )

        capture_mode_record_name = EpicsName(self.DATA_PREFIX + ":CAPTURE_MODE")
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
            record_prefix + ":" + self.DATA_PREFIX + ":CaptureMode"
        )

        status_message_record_name = EpicsName(self.DATA_PREFIX + ":STATUS")
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
            record_prefix + ":" + self.DATA_PREFIX + ":Status"
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

    async def _update_directory_path(self, new_val) -> None:
        """Handles writes to the directory path PV, creating
        directories based on the setting of the CreateDirectory record"""
        new_path = Path(new_val).absolute()
        create_dir_depth = self._create_directory_record.get()
        max_dirs_to_create = 0
        if create_dir_depth < 0:
            max_dirs_to_create = abs(create_dir_depth)
        elif create_dir_depth > len(new_path.parents):
            max_dirs_to_create = 0
        elif create_dir_depth > 0:
            max_dirs_to_create = len(new_path.parents) - create_dir_depth

        logging.debug(f"Permitted to create up to {max_dirs_to_create} dirs.")
        dirs_to_create = 0
        for p in reversed(new_path.parents):
            if not p.exists():
                if dirs_to_create == 0:
                    # First directory level that does not exist, log it.
                    logging.error(f"All dir from {str(p)} and below do not exist!")
                dirs_to_create += 1
            else:
                logging.info(f"{str(p)} exists")

        # Account for target path itself not existing
        if not os.path.exists(new_path):
            dirs_to_create += 1

        logging.debug(f"Need to create {dirs_to_create} directories.")

        # Case where all dirs exist
        if dirs_to_create == 0:
            if os.access(new_path, os.W_OK):
                status_msg = "Dir exists and is writable"
                self._directory_exists_record.set(1)
            else:
                status_msg = "Dirs exist but aren't writable."
                self._directory_exists_record.set(0)
        # Case where we will create directories
        elif dirs_to_create <= max_dirs_to_create:
            logging.debug(f"Attempting to create {dirs_to_create} dir(s)...")
            try:
                os.makedirs(new_path, exist_ok=True)
                status_msg = f"Created {dirs_to_create} dirs."
                self._directory_exists_record.set(1)
            except PermissionError:
                status_msg = "Permission error creating dirs!"
                self._directory_exists_record.set(0)
        # Case where too many directories need to be created
        else:
            status_msg = f"Need to create {dirs_to_create} > {max_dirs_to_create} dirs."
            self._directory_exists_record.set(0)

        if self._directory_exists_record.get() == 0:
            sevr, alrm = alarm.MAJOR_ALARM, alarm.STATE_ALARM
            logging.error(status_msg)
        else:
            sevr, alrm = alarm.NO_ALARM, alarm.NO_ALARM
            logging.debug(status_msg)

        self._status_message_record.set(status_msg, severity=sevr, alarm=alrm)

        await self._update_full_file_path(new_val)

    async def _update_full_file_path(self, new_val) -> None:
        self._full_file_path_record.set(self._get_filepath())

    async def _handle_hdf5_data(self) -> None:
        """Handles writing HDF5 data from the PandA to file, based on configuration
        in the various HDF5 records.
        This method expects to be run as an asyncio Task."""
        try:
            # Set up the hdf buffer

            if not self._directory_exists_record.get() == 1:
                raise RuntimeError(
                    "Configured HDF directory does not exist or is not writable!"
                )

            num_capture: int = self._num_capture_record.get()
            capture_mode: CaptureMode = CaptureMode(self._capture_mode_record.get())
            filepath = self._get_filepath()

            number_captured_setter_pipeline = NumCapturedSetter(
                self._num_captured_record.set
            )

            # Update `DATA:DATASETS` to match the names of the datasets
            # in the HDF5 file
            self._datasets.update_datasets_record()

            buffer = HDF5Buffer(
                capture_mode,
                filepath,
                num_capture,
                self._status_message_record.set,
                self._num_received_record.set,
                number_captured_setter_pipeline,
                self._datasets.hdf_writer_names(),
            )
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
            if buffer.capture_mode != CaptureMode.LAST_N:
                buffer.put_data_to_file(
                    EndData(buffer.number_of_received_rows, EndReason.MANUALLY_STOPPED)
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
            if buffer.start_data and buffer.capture_mode != CaptureMode.LAST_N:
                buffer.put_data_to_file(
                    EndData(buffer.number_of_received_rows, EndReason.UNKNOWN_EXCEPTION)
                )

        finally:
            logging.debug("Finishing processing HDF5 PandA data")
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
