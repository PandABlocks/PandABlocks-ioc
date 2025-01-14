# Creating EPICS records directly from PandA Blocks and Fields
import asyncio
import inspect
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from string import digits
from typing import Any, Optional

import numpy as np
from pandablocks.asyncio import AsyncioClient
from pandablocks.commands import (
    Arm,
    ChangeGroup,
    Disarm,
    Get,
    GetBlockInfo,
    GetChanges,
    GetFieldInfo,
    Put,
)
from pandablocks.responses import (
    BitMuxFieldInfo,
    BitOutFieldInfo,
    BlockInfo,
    Changes,
    EnumFieldInfo,
    ExtOutBitsFieldInfo,
    ExtOutFieldInfo,
    FieldInfo,
    PosMuxFieldInfo,
    PosOutFieldInfo,
    ScalarFieldInfo,
    SubtypeTimeFieldInfo,
    TableFieldInfo,
    TimeFieldInfo,
    UintFieldInfo,
)
from softioc import alarm, asyncio_dispatcher, builder, fields, softioc
from softioc.imports import db_put_field
from softioc.pythonSoftIoc import RecordWrapper

from ._connection_status import ConnectionStatus, Statuses
from ._hdf_ioc import Dataset, HDF5RecordController
from ._pvi import (
    Pvi,
    PviGroup,
    add_automatic_pvi_info,
    add_pcap_arm_pvi_info,
    add_positions_table_row,
)
from ._tables import TableRecordWrapper, TableUpdater
from ._types import (
    ONAM_STR,
    OUT_RECORD_FUNCTIONS,
    ZNAM_STR,
    EpicsName,
    InErrorException,
    PandAName,
    RecordInfo,
    RecordValue,
    ScalarRecordValue,
    check_num_labels,
    device_and_record_to_panda_name,
    panda_to_epics_name,
    trim_description,
    trim_string_value,
)
from ._version import __version__

# TODO: Try turning python.analysis.typeCheckingMode on, as it does highlight a couple
# of possible errors


@dataclass
class _BlockAndFieldInfo:
    """Contains all available information for a Block, including Fields and all the
    Values for `block_info.number` instances of the Fields."""

    block_info: BlockInfo
    fields: dict[str, FieldInfo]
    values: dict[EpicsName, RecordValue]


# Keep a reference to the task, as specified in documentation:
# https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task
create_softioc_task: Optional[asyncio.Task] = None


def _when_finished(task):
    global create_softioc_task
    create_softioc_task = None


async def _create_softioc(
    client: AsyncioClient,
    record_prefix: str,
    connection_status: ConnectionStatus,
    dispatcher: asyncio_dispatcher.AsyncioDispatcher,
):
    """Asynchronous wrapper for IOC creation"""
    try:
        await client.connect()
    except OSError:
        logging.exception("Unable to connect to PandA")
        raise
    (all_records, all_values_dict, block_info_dict) = await create_records(
        client, dispatcher, record_prefix
    )

    global create_softioc_task
    if create_softioc_task:
        raise RuntimeError("Unexpected state - softioc task already exists")

    create_softioc_task = asyncio.create_task(
        update(
            client,
            connection_status,
            all_records,
            0.1,
            all_values_dict,
            block_info_dict,
        )
    )

    create_softioc_task.add_done_callback(_when_finished)


def create_softioc(
    client: AsyncioClient,
    record_prefix: str,
    screens_dir: Optional[str] = None,
    clear_bobfiles: bool = False,
) -> None:
    """Create a PythonSoftIOC from fields and attributes of a PandA.

    This function will introspect a PandA for all defined Blocks, Fields of each Block,
    and Attributes of each Field, and create appropriate EPICS records for each.

    Args:
        client: The asyncio client to be used to read/write to of the PandA
        record_prefix: The string prefix used for creation of all records.
        screens_dir: The directory to export bobfiles to.
        clear_bobfiles: Can only be true if screens_dir is provided. Clears the
            screens_dir of bobfiles before creating new ones.
    """
    # TODO: This needs to read/take in a YAML configuration file, for various aspects
    # e.g. the update() wait time between calling GetChanges

    if clear_bobfiles and not screens_dir:
        raise ValueError("recieved clear_bobfiles=True with no screens_dir")

    if screens_dir:
        Pvi.configure_pvi(screens_dir, clear_bobfiles)

    try:
        dispatcher = asyncio_dispatcher.AsyncioDispatcher()
        connection_status = ConnectionStatus(record_prefix)
        connection_status.set_status(Statuses.CONNECTING)
        asyncio.run_coroutine_threadsafe(
            _create_softioc(client, record_prefix, connection_status, dispatcher),
            dispatcher.loop,
        ).result()
        connection_status.set_status(Statuses.CONNECTED)

        # Must leave this blocking line here, in the main thread, not in the
        # dispatcher's loop or it'll block every async process in this module
        softioc.interactive_ioc(globals())
    except OSError as exc:
        logging.exception("Exception while initializing softioc")
        connection_status.set_status(Statuses.DISCONNECTED)
        raise exc
    finally:
        # Client was connected in the _create_softioc method
        if client.is_connected():
            asyncio.run_coroutine_threadsafe(client.close(), dispatcher.loop).result()


def get_panda_versions(idn_repsonse: str) -> dict[EpicsName, str]:
    """Function that parses version info from the PandA's response to the IDN command

    See: https://pandablocks-server.readthedocs.io/en/latest/commands.html#system-commands

    Args:
        idn_response (str): Response from PandA to Get(*IDN) command

    Returns:
        dict[EpicsName, str]: Dictionary mapping firmware record name to version
    """

    # Currently, IDN reports sw, fpga, and rootfs versions
    firmware_versions = {"PandA SW": "Unknown", "FPGA": "Unknown", "rootfs": "Unknown"}

    # If the *IDN response contains too many keys, break and leave versions as "Unknown"
    # Since spaces are used to deliminate versions and can also be in the keys and
    # values, if an additional key is present that we don't explicitly handle,
    # our approach of using regex matching will not work.
    if sum(name in idn_repsonse for name in firmware_versions) < idn_repsonse.count(
        ":"
    ):
        logging.error(
            f"Recieved unexpected version numbers in version string {idn_repsonse}!"
        )
    else:
        for firmware_name in firmware_versions:
            pattern = re.compile(
                rf'{re.escape(firmware_name)}:\s*([^:]+?)(?=\s*\b(?: \
                {"|".join(map(re.escape, firmware_versions))}):|$)'
            )
            if match := pattern.search(idn_repsonse):
                firmware_versions[firmware_name] = match.group(1).strip()
                logging.info(
                    f"{firmware_name} Version: {firmware_versions[firmware_name]}"
                )
            else:
                logging.warning(f"Failed to get {firmware_name} version information!")

    return {
        EpicsName(firmware_name.upper().replace(" ", "_")): version
        for firmware_name, version in firmware_versions.items()
    }


async def introspect_panda(
    client: AsyncioClient,
) -> tuple[dict[str, _BlockAndFieldInfo], dict[EpicsName, RecordValue]]:
    """Query the PandA for all its Blocks, Fields of each Block, and Values of each
    Field

    Args:
        client (AsyncioClient): Client used for commuication with the PandA

    Returns:
        Tuple of:
            Dict[str, BlockAndFieldInfo]: Dictionary containing all information on
                the block
            Dict[EpicsName, RecordValue]]: Dictionary containing all values from
                GetChanges for both scalar and multivalue fields
    """

    block_dict = await client.send(GetBlockInfo())

    for block in block_dict.keys():
        if block[-1].isdigit():
            raise ValueError(f"Block name '{block}' contains a trailing number")

    # Concurrently request info for all fields of all blocks
    # Note order of requests is important as it is unpacked by index below
    returned_infos = await asyncio.gather(
        *[client.send(GetFieldInfo(block)) for block in block_dict],
        client.send(GetChanges(ChangeGroup.ALL, True)),
    )

    field_infos: list[dict[str, FieldInfo]] = returned_infos[0:-1]

    changes: Changes = returned_infos[-1]

    values, all_values_dict = _create_dicts_from_changes(changes, block_dict)

    panda_dict = {
        block_name: _BlockAndFieldInfo(block_info, field_info, values[block_name])
        for (block_name, block_info), field_info in zip(
            block_dict.items(), field_infos, strict=False
        )
    }

    return (panda_dict, all_values_dict)


def extract_label_from_metadata(block_name_number, field_name: str):
    # Parse *METADATA.LABEL_<block><num> into "<block>" key and
    # "<block><num>:LABEL" value
    if block_name_number.startswith("*METADATA") and field_name.startswith("LABEL_"):
        _, block_name_number = field_name.split("_", maxsplit=1)

        # The block is fixed with metadata, it should end with a number
        #     "*METADATA.LABEL_SEQ2": "NewSeqMetadataLabel",
        if not block_name_number[-1].isdigit():
            raise ValueError(
                f"Recieved metadata for a block name {block_name_number} that "
                "didn't contain a number"
            )

        return block_name_number
    return None


def _create_dicts_from_changes(
    changes: Changes, block_info_dict: dict[str, BlockInfo]
) -> tuple[dict[str, dict[EpicsName, RecordValue]], dict[EpicsName, RecordValue]]:
    """Take the `Changes` object and convert it into two dictionaries.

    Args:
        changes: The `Changes` object as returned by `GetChanges`
        block_info_dict: Information from the initial `GetBlockInfo` request,
            used to check the `number` of blocks for parsing metadata

    Returns:
        Tuple of:
          Dict[str, Dict[EpicsName, RecordValue]]: Block-level dictionary, where each
            top-level key is a PandA Block, and the inner dictionary is all the fields
            and values associated with that Block.
          Dict[EpicsName, RecordValue]]: A flattened version of the above dictionary -
            a list of all Fields (across all Blocks) and their associated value.
    """

    def _store_values(
        block_and_field_name: str,
        value: RecordValue,
        values: dict[str, dict[EpicsName, RecordValue]],
    ) -> None:
        """Parse the data given in `block_and_field_name` and `value` into a new entry
        in the `values` dictionary"""

        block_name_number, field_name = block_and_field_name.split(".", maxsplit=1)

        if label_block_name_number := extract_label_from_metadata(
            block_name_number, field_name
        ):
            block_name_number = label_block_name_number
            block_name_no_number = re.sub(r"\d*$", "", label_block_name_number)

            number_of_blocks = block_info_dict[block_name_no_number].number

            if number_of_blocks == 1:
                if block_name_number[-1] != "1" or block_name_number[-2].isdigit():
                    raise ValueError(
                        f"Recieved metadata '*METADATA.LABEL_{block_name_number}', "
                        "this should have a single '1' on the end"
                    )
                block_and_field_name = EpicsName(block_name_number[:-1] + ":LABEL")
            else:
                block_and_field_name = EpicsName(block_name_number + ":LABEL")

        else:
            block_and_field_name = panda_to_epics_name(PandAName(block_and_field_name))

        block_name = block_name_number.rstrip(digits)

        if block_name not in values:
            values[block_name] = {}
        if block_and_field_name in values[block_name]:
            logging.error(
                f"Duplicate values for {block_and_field_name} detected."
                " Overriding existing value."
            )
        block_and_field_name = EpicsName(block_and_field_name)
        values[block_name][block_and_field_name] = value

    # Create a dict which maps block name to all values for all instances
    # of that block (e.g. {"TTLIN" : {"TTLIN1:VAL": "1", "TTLIN2:VAL" : "5", ...} })
    values: dict[str, dict[EpicsName, RecordValue]] = {}
    for block_and_field_name, value in changes.values.items():
        _store_values(block_and_field_name, value, values)

    # Parse the multiline data into the same values structure
    for block_and_field_name, multiline_value in changes.multiline_values.items():
        _store_values(block_and_field_name, multiline_value, values)

    # Note any in_error fields so we can later set their records to a non-zero severity
    for block_and_field_name in changes.in_error:
        logging.error(f"PandA reports field in error: {block_and_field_name}")
        _store_values(
            block_and_field_name, InErrorException(block_and_field_name), values
        )

    # Single dictionary that has all values for all types of field, as reported
    # from GetChanges
    all_values_dict = {k: v for item in values.values() for k, v in item.items()}
    return values, all_values_dict


@dataclass
class _RecordUpdater:
    """Handles Put'ing data back to the PandA when an EPICS record is updated.

    This should only be used to handle Out record types.

    Args:
        record_info: The RecordInfo structure for the record
        record_prefix: The prefix of the record name
        client: The client used to send data to PandA
        all_values_dict: The dictionary containing the most recent value of all records
            as returned from GetChanges. This dict will be dynamically updated by other
            methods.
        labels: If the record is an enum type, provide the list of labels
    """

    record_info: RecordInfo
    record_prefix: str
    client: AsyncioClient
    all_values_dict: dict[EpicsName, RecordValue]
    labels: Optional[list[str]]

    # The incoming value's type depends on the record. Ensure you always cast it.
    async def update(self, new_val: Any):
        logging.debug(
            f"Updating record {self.record_info.record.name} with value {new_val}"
        )
        try:
            # If this is an enum record, retrieve the string value
            val: Optional[str]
            if self.labels:
                assert int(new_val) < len(
                    self.labels
                ), f"Invalid label index {new_val}, only {len(self.labels)} labels"
                val = self.labels[int(new_val)]
            elif new_val is not None:
                # Necessary to wrap the data_type_func call in str() as we must
                # differentiate between ints and floats - some PandA fields will not
                # accept the wrong number format.
                val = str(self.record_info.data_type_func(new_val))

            else:
                # value is None - expected for action-write fields
                val = new_val

            record_name = self.record_info.record.name.removeprefix(self.record_prefix)
            panda_field = device_and_record_to_panda_name(record_name)

            await self.client.send(Put(panda_field, val))

            self.record_info._pending_change = True

            # On success the new value will be polled by GetChanges and stored into
            # the all_values_dict

        except Exception:
            logging.exception(
                f"Unable to Put record {self.record_info.record.name}, "
                f"value {new_val}, to PandA",
            )
            try:
                if self.record_info.record:
                    record_name = self.record_info.record.name.removeprefix(
                        self.record_prefix + ":"
                    )

                    assert record_name in self.all_values_dict
                    old_val = self.all_values_dict[record_name]
                    if isinstance(old_val, InErrorException):
                        # If PythonSoftIOC issue #53 is fixed we could put error state.
                        logging.error(
                            "Cannot restore previous value to record "
                            f"{record_name}, PandA field is in error."
                        )
                        return

                    logging.warning(
                        f"Restoring previous value {old_val} to record {record_name}"
                    )
                    # Note that only Out records will be present here, due to how
                    # _RecordUpdater instances are created.
                    self.record_info.record.set(old_val, process=False)
                else:
                    logging.error(
                        f"No record found when updating {record_name},"
                        " unable to roll back value"
                    )
            except Exception:
                logging.exception(
                    f"Unable to roll back record {record_name} to previous value.",
                )


@dataclass
class _WriteRecordUpdater(_RecordUpdater):
    """Special case record updater to send an empty value.

    This is necessary as some PandA fields are written using e.g. \"FOO1.BAR=\"
    with no explicit value at all."""

    async def update(self, new_val):
        await super().update(None)


@dataclass
class _TimeRecordUpdater(_RecordUpdater):
    """Set the EGU values on a record when the UNITS sub-record is updated."""

    base_record: RecordWrapper
    is_type_time: bool

    async def update(self, new_val: Any):
        # Must allow UNITS value change to be pushed to the PandA
        # as this triggers the MIN field to be recalculated
        await super().update(new_val)

        await self.update_parent_record(new_val)

    async def update_parent_record(self, new_val):
        self.update_egu(new_val)

    def update_egu(self, new_val) -> None:
        assert self.labels

        # This method gets called in two contexts: One is directly from an EPICS
        # on_update and the other is from *CHANGES?.
        # In the EPICS context, the value is an integer (from an mbbi/o record)
        # In the *CHANGES? context the value is a string
        if isinstance(new_val, str):
            assert new_val in self.labels
            new_egu = new_val
        else:
            new_egu = self.labels[new_val]
        array = np.require(new_egu, dtype=np.dtype("S40"))
        db_put_field(
            f"{self.base_record.name}.EGU",
            fields.DBF_STRING,
            array.ctypes.data,
            1,
        )


@dataclass
class StringRecordLabelValidator:
    """Validate that a given string is a valid label for a PandA enum field.
    This is necessary for several fields which have too many labels to fit in
    an EPICS mbbi/mbbo record, and so use string records instead."""

    labels: list[str]

    def validate(self, record: RecordWrapper, new_val: str):
        if new_val in self.labels:
            return True
        logging.error(f"Value {new_val} not valid for record {record.name}")
        return False


class IocRecordFactory:
    """Class to handle creating PythonSoftIOC records for a given field defined in
    a PandA"""

    _record_prefix: str
    _client: AsyncioClient
    _all_values_dict: dict[EpicsName, RecordValue]
    _pos_out_row_counter: int = 0

    # List of methods in builder, used for parameter validation
    _builder_methods = [
        method
        for _, method in inspect.getmembers(builder, predicate=inspect.isfunction)
    ]

    def __init__(
        self,
        client: AsyncioClient,
        record_prefix: str,
        all_values_dict: dict[EpicsName, RecordValue],
    ):
        """Initialise IocRecordFactory

        Args:
            client: AsyncioClient used when records update to Put values back to PandA
            record_prefix: The record prefix a.k.a. the device name
            all_values_dict: Dictionary of most recent values from PandA as reported by
                GetChanges.
        """
        self._record_prefix = record_prefix
        self._client = client
        self._all_values_dict = all_values_dict

        # Set the record prefix
        builder.SetDeviceName(self._record_prefix)
        Pvi.record_prefix = self._record_prefix

        # All records should be blocking
        builder.SetBlocking(True)

        # A dataset cache for storing dataset names and capture modes for different
        # capture records
        self._dataset_cache: dict[EpicsName, Dataset] = {}

    def _process_labels(
        self, labels: list[str], record_value: ScalarRecordValue
    ) -> tuple[list[str], int]:
        """Find the index of `record_value` in the `labels` list, suitable for
        use in an `initial_value=` argument during record creation.
        Secondly, return a new list from the given labels that are all short
        enough to fit within EPICS 25 character label limit.

        Raises ValueError if `record_value` not found in `labels`."""
        assert len(labels) > 0

        if not all(len(label) < 25 for label in labels):
            logging.warning(
                "One or more labels do not fit EPICS maximum length of "
                f"25 characters. Long labels will be truncated. Labels: {labels}"
            )

        # Most likely time we'll see an error is when PandA hardware has set invalid
        # enum value. No logging as already logged when seen from GetChanges.
        if isinstance(record_value, InErrorException):
            index = 0
        else:
            index = labels.index(record_value)

        return ([label[:25] for label in labels], index)

    def _check_num_values(
        self, values: dict[EpicsName, ScalarRecordValue], num: int
    ) -> None:
        """Function to check that the number of values is at least the expected amount.
        Allow extra values for future-proofing, if PandA has new fields/attributes the
        client does not know about.
        Raises AssertionError if too few values."""
        assert len(values) >= num, (
            f"Incorrect number of values, {len(values)}, expected at least {num}.\n"
            + f"{values}"
        )

    def _create_record_info(
        self,
        record_name: EpicsName,
        description: Optional[str],
        record_creation_func: Callable,
        data_type_func: Callable,
        group: PviGroup,
        labels: Optional[list[str]] = None,
        *args,
        **kwargs,
    ) -> RecordInfo:
        """Create the record, using the given function and passing all optional
        arguments and keyword arguments, and then set the description field for the
        record.
        If the record is an Out type, a default on_update mechanism will be added. This
        can be overriden by specifying a custom "on_update=..." keyword.

        Args:
            record_name: The name this record will be created with
            description: The description for this field. This will be truncated
                to 40 characters due to EPICS limitations.
            record_creation_func: The function that will be used to create
                this record. Must be one of the builder.* functions.
            data_type_func: The function to use to convert the value returned
                from GetChanges, which will always be a string, into a type appropriate
                for the record e.g. int, float.
            group: The group that this record will be displayed in for PVI.
            labels: If the record type being created is a mbbi or mbbo
                record, provide the list of valid labels here.
            *args: Additional arguments that will be passed through to the
                `record_creation_func`
            **kwargs: Additional keyword arguments that will be examined and possibly
                modified for various reasons, and then passed to the
                `record_creation_func`

        Returns:
            RecordInfo: Class containing the created record and anything needed for
                updating the record.
        """
        if labels is None:
            labels = []

        extra_kwargs: dict[str, Any] = {}
        assert (
            record_creation_func in self._builder_methods
        ), "Unrecognised record creation function passed to _create_record_info"

        if (
            record_creation_func == builder.mbbIn
            or record_creation_func == builder.mbbOut
        ):
            check_num_labels(labels, record_name)

        # Check the initial value is valid. If it is, apply data type conversion
        # otherwise mark the record as in error.
        # Note that many already have correct type, this mostly applies to values
        # that are being sent as strings to analog or long records as the values are
        # returned as strings from Changes command.
        if "initial_value" in kwargs:
            initial_value = kwargs["initial_value"]
            if isinstance(initial_value, InErrorException):
                logging.warning(
                    f"Marking record {record_name} as invalid due to error from PandA"
                )
                # See PythonSoftIOC issue #57
                extra_kwargs.update({"STAT": "UDF", "SEVR": "INVALID"})
                kwargs.pop("initial_value")
            elif record_creation_func in [builder.stringIn, builder.stringOut]:
                kwargs["initial_value"] = trim_string_value(initial_value, record_name)
            elif isinstance(initial_value, str):
                kwargs["initial_value"] = data_type_func(initial_value)

        record_info = RecordInfo(
            data_type_func=data_type_func,
            labels=labels if labels else None,
            is_in_record=record_creation_func not in OUT_RECORD_FUNCTIONS,
        )

        # If there is no on_update, and the record type allows one, create it
        record_updater = None
        if (
            "on_update" not in kwargs
            and "on_update_name" not in kwargs
            and record_creation_func in OUT_RECORD_FUNCTIONS
        ):
            record_updater = _RecordUpdater(
                record_info,
                self._record_prefix,
                self._client,
                self._all_values_dict,
                labels if labels else None,
            )
            extra_kwargs["on_update"] = record_updater.update

        extra_kwargs["DESC"] = trim_description(description, record_name)

        record = record_creation_func(
            record_name, *labels, *args, **extra_kwargs, **kwargs
        )

        add_automatic_pvi_info(
            group=group,
            record=record,
            record_name=record_name,
            record_creation_func=record_creation_func,
        )

        # Annoyingly we have a circular dependency: The on_update kwarg must be provided
        # in order to create the record
        record_info.add_record(record)

        return record_info

    def _make_time(
        self,
        record_name: EpicsName,
        field_info: FieldInfo,
        values: dict[EpicsName, ScalarRecordValue],
        record_creation_func: Callable,
        **kwargs,
    ) -> dict[EpicsName, RecordInfo]:
        """Make one record for the timer itself, and a sub-record for its units"""
        assert isinstance(field_info, (TimeFieldInfo, SubtypeTimeFieldInfo))

        record_dict: dict[EpicsName, RecordInfo] = {}

        time_record_info = self._create_record_info(
            record_name,
            field_info.description,
            record_creation_func,
            float,
            PviGroup.PARAMETERS,
            **kwargs,
        )

        record_dict[record_name] = time_record_info

        units_record_name = EpicsName(record_name + ":UNITS")
        labels, initial_index = self._process_labels(
            field_info.units_labels, values[units_record_name]
        )

        # Ensure initial EGU matches that of the :UNITS record
        time_record_info.record.EGU = labels[initial_index]

        updater: _TimeRecordUpdater

        record_dict[units_record_name] = self._create_record_info(
            units_record_name,
            "Units of time setting",
            builder.mbbOut,
            type(initial_index),
            PviGroup.PARAMETERS,
            labels=labels,
            initial_value=initial_index,
            on_update=lambda v: updater.update(v),
        )
        updater = _TimeRecordUpdater(
            record_dict[units_record_name],
            self._record_prefix,
            self._client,
            self._all_values_dict,
            labels,
            time_record_info.record,
            isinstance(field_info, TimeFieldInfo),
        )

        record_dict[units_record_name].on_changes_func = updater.update_parent_record

        return record_dict

    def _make_type_time(
        self,
        record_name: EpicsName,
        field_info: FieldInfo,
        values: dict[EpicsName, ScalarRecordValue],
    ) -> dict[EpicsName, RecordInfo]:
        """Make the records for a field of type "time" - one for the time itself, one
        for units, and one for the MIN value.
        """
        # RAW attribute ignored - EPICS should never care about it
        self._check_num_values(values, 2)
        assert isinstance(field_info, TimeFieldInfo)
        record_dict = self._make_time(
            record_name,
            field_info,
            values,
            builder.aOut,
            initial_value=values[record_name],
        )

        return record_dict

    def _make_subtype_time_param(
        self,
        record_name: EpicsName,
        field_info: FieldInfo,
        values: dict[EpicsName, ScalarRecordValue],
    ) -> dict[EpicsName, RecordInfo]:
        self._check_num_values(values, 2)
        return self._make_time(
            record_name,
            field_info,
            values,
            builder.aOut,
            initial_value=values[record_name],
        )

    def _make_subtype_time_read(
        self,
        record_name: EpicsName,
        field_info: FieldInfo,
        values: dict[EpicsName, ScalarRecordValue],
    ) -> dict[EpicsName, RecordInfo]:
        self._check_num_values(values, 2)
        return self._make_time(
            record_name,
            field_info,
            values,
            builder.aIn,
            initial_value=values[record_name],
        )

    def _make_subtype_time_write(
        self,
        record_name: EpicsName,
        field_info: FieldInfo,
        values: dict[EpicsName, ScalarRecordValue],
    ) -> dict[EpicsName, RecordInfo]:
        self._check_num_values(values, 1)
        return self._make_time(record_name, field_info, values, builder.aOut)

    def _make_bit_out(
        self,
        record_name: EpicsName,
        field_info: FieldInfo,
        values: dict[EpicsName, ScalarRecordValue],
    ) -> dict[EpicsName, RecordInfo]:
        self._check_num_values(values, 1)
        assert isinstance(field_info, BitOutFieldInfo)

        record_dict: dict[EpicsName, RecordInfo] = {}
        record_dict[record_name] = self._create_record_info(
            record_name,
            field_info.description,
            builder.boolIn,
            int,
            PviGroup.OUTPUTS,
            ZNAM=ZNAM_STR,
            ONAM=ONAM_STR,
            initial_value=values[record_name],
        )

        # TODO: Add BITS table support here

        return record_dict

    def _make_pos_out(
        self,
        record_name: EpicsName,
        field_info: FieldInfo,
        values: dict[EpicsName, ScalarRecordValue],
    ) -> dict[EpicsName, RecordInfo]:
        self._check_num_values(values, 5)
        assert isinstance(field_info, PosOutFieldInfo)
        record_dict: dict[EpicsName, RecordInfo] = {}

        units_record_name = EpicsName(record_name + ":UNITS")
        record_dict[record_name] = self._create_record_info(
            record_name,
            field_info.description,
            builder.longIn,
            int,
            PviGroup.OUTPUTS,
            initial_value=values[record_name],
            EGU=values[units_record_name],
        )

        capture_record_name = EpicsName(record_name + ":CAPTURE")
        dataset_record_name = EpicsName(record_name + ":DATASET")
        labels, capture_index = self._process_labels(
            field_info.capture_labels, values[capture_record_name]
        )

        capture_record_updater: _RecordUpdater

        def capture_record_on_update(new_capture_mode):
            self._dataset_cache[record_name] = Dataset(
                record_dict[dataset_record_name].record.get(),
                labels[new_capture_mode],
            )
            return capture_record_updater.update(new_capture_mode)

        record_dict[capture_record_name] = self._create_record_info(
            capture_record_name,
            "Capture options",
            builder.mbbOut,
            int,
            PviGroup.CAPTURE,
            labels=labels,
            initial_value=capture_index,
            on_update=capture_record_on_update,
        )

        # For now we have to make a `_RecordUpdater`` here and
        # combine it with `on_update`.
        # https://github.com/PandABlocks/PandABlocks-ioc/issues/121
        capture_record_updater = _RecordUpdater(
            record_dict[capture_record_name],
            self._record_prefix,
            self._client,
            self._all_values_dict,
            labels if labels else None,
        )

        def dataset_record_on_update(new_dataset_name):
            self._dataset_cache[record_name] = Dataset(
                new_dataset_name,
                labels[record_dict[capture_record_name].record.get()],
            )

        record_dict[dataset_record_name] = self._create_record_info(
            dataset_record_name,
            "Used to adjust the dataset name to one more scientifically relevant",
            builder.stringOut,
            str,
            PviGroup.CAPTURE,
            initial_value="",
            on_update=dataset_record_on_update,
        )

        offset_record_name = EpicsName(record_name + ":OFFSET")
        record_dict[offset_record_name] = self._create_record_info(
            offset_record_name,
            "Offset",
            builder.aOut,
            float,
            PviGroup.CAPTURE,
            initial_value=values[offset_record_name],
        )

        scale_record_name = EpicsName(record_name + ":SCALE")
        record_dict[scale_record_name] = self._create_record_info(
            scale_record_name,
            "Scale factor",
            builder.aOut,
            float,
            PviGroup.CAPTURE,
            initial_value=values[scale_record_name],
        )

        record_dict[units_record_name] = self._create_record_info(
            units_record_name,
            "Units string",
            builder.stringOut,
            str,
            PviGroup.CAPTURE,
            initial_value=values[units_record_name],
        )

        # SCALED attribute doesn't get returned from GetChanges. Instead
        # of trying to dynamically query for it we'll just recalculate it
        scaled_record_name = record_name + ":SCALED"
        scaled_calc_record = builder.records.calc(
            scaled_record_name,
            CALC="A*B + C",
            INPA=builder.CP(record_dict[record_name].record),
            INPB=builder.CP(record_dict[scale_record_name].record),
            INPC=builder.CP(record_dict[offset_record_name].record),
            DESC="Value with scaling applied",
            PREC=5,
        )

        # Create the POSITIONS "table" of records. Most are aliases of the records
        # created above.
        positions_record_name = f"POSITIONS:{self._pos_out_row_counter}"
        builder.records.stringin(
            positions_record_name + ":NAME",
            VAL=record_name,
            DESC="Table of configured positional outputs",
        )

        value_record_name = EpicsName(positions_record_name + ":VAL")
        scaled_calc_record.add_alias(self._record_prefix + ":" + value_record_name)

        record_dict[capture_record_name].record.add_alias(
            self._record_prefix
            + ":"
            + positions_record_name
            + ":"
            + capture_record_name.split(":")[-1]
        )
        record_dict[offset_record_name].record.add_alias(
            self._record_prefix
            + ":"
            + positions_record_name
            + ":"
            + offset_record_name.split(":")[-1]
        )
        record_dict[scale_record_name].record.add_alias(
            self._record_prefix
            + ":"
            + positions_record_name
            + ":"
            + scale_record_name.split(":")[-1]
        )
        record_dict[units_record_name].record.add_alias(
            self._record_prefix
            + ":"
            + positions_record_name
            + ":"
            + units_record_name.split(":")[-1]
        )
        record_dict[dataset_record_name].record.add_alias(
            self._record_prefix
            + ":"
            + positions_record_name
            + ":"
            + dataset_record_name.split(":")[-1]
        )

        self._pos_out_row_counter += 1
        add_positions_table_row(
            record_name,
            value_record_name,
            units_record_name,
            scale_record_name,
            offset_record_name,
            dataset_record_name,
            capture_record_name,
        )

        return record_dict

    def _make_ext_out(
        self,
        record_name: EpicsName,
        field_info: FieldInfo,
        values: dict[EpicsName, ScalarRecordValue],
    ) -> dict[EpicsName, RecordInfo]:
        self._check_num_values(values, 1)
        assert isinstance(field_info, ExtOutFieldInfo)
        record_dict: dict[EpicsName, RecordInfo] = {}

        # There is no record for the ext_out field itself - the only thing
        # you do with them is to turn their Capture attribute on/off, and give it
        # an alternative dataset name

        capture_record_name = EpicsName(record_name + ":CAPTURE")
        dataset_record_name = EpicsName(record_name + ":DATASET")
        labels, capture_index = self._process_labels(
            field_info.capture_labels, values[capture_record_name]
        )

        def dataset_record_on_update(new_dataset_name):
            self._dataset_cache[record_name] = Dataset(
                new_dataset_name,
                labels[record_dict[capture_record_name].record.get()],
            )

        record_dict[dataset_record_name] = self._create_record_info(
            dataset_record_name,
            "Used to adjust the dataset name to one more scientifically relevant",
            builder.stringOut,
            str,
            PviGroup.OUTPUTS,
            initial_value="",
            on_update=dataset_record_on_update,
        )

        capture_record_updater: _RecordUpdater

        def capture_record_on_update(new_capture_mode):
            self._dataset_cache[record_name] = Dataset(
                record_dict[dataset_record_name].record.get(),
                labels[new_capture_mode],
            )
            return capture_record_updater.update(new_capture_mode)

        record_dict[capture_record_name] = self._create_record_info(
            capture_record_name,
            field_info.description,
            builder.mbbOut,
            int,
            PviGroup.OUTPUTS,
            labels=labels,
            initial_value=capture_index,
            on_update=capture_record_on_update,
        )
        # For now we have to make a `_RecordUpdater`` here and
        # combine it with `on_update`.
        # https://github.com/PandABlocks/PandABlocks-ioc/issues/121
        capture_record_updater = _RecordUpdater(
            record_dict[capture_record_name],
            self._record_prefix,
            self._client,
            self._all_values_dict,
            labels if labels else None,
        )

        return record_dict

    def _make_ext_out_bits(
        self,
        record_name: EpicsName,
        field_info: FieldInfo,
        values: dict[EpicsName, ScalarRecordValue],
    ) -> dict[EpicsName, RecordInfo]:
        self._check_num_values(values, 1)
        assert isinstance(field_info, ExtOutBitsFieldInfo)

        record_dict = self._make_ext_out(record_name, field_info, values)

        # Create a "table" out of the items present in the list of bits

        # Identify which BITS field this is and calculate its offset - we want BITS0
        # through BITS3 to look like one continuous table from the outside, indexed
        # 0 through 127 (each BITS holds 32 values)
        bits_index_str = record_name[-1]
        assert bits_index_str.isdigit()
        bits_index = int(bits_index_str)
        offset = bits_index * 32

        capture_record_name = EpicsName(record_name + ":CAPTURE")
        capture_record_info = record_dict[capture_record_name]

        # There is a single CAPTURE record which is alias'd to appear in each row.
        # This is because you can only capture a whole field's worth of bits at a time,
        # and not bits individually. When one is captured, they all are.
        for i in range(offset, offset + 32):
            capture_record_info.record.add_alias(
                f"{self._record_prefix}:BITS:{i}:CAPTURE"
            )

        # Each row of the table has a VAL and a NAME.
        for i, label in enumerate(field_info.bits):
            if label == "":
                # Some rows are empty. Do not create records.
                continue
            link = self._record_prefix + ":" + label.replace(".", ":") + " CP"
            enumerated_bits_prefix = f"BITS:{offset + i}"
            builder.records.bi(
                f"{enumerated_bits_prefix}:VAL",
                INP=link,
                DESC="Value of field connected to this BIT",
                ZNAM=ZNAM_STR,
                ONAM=ONAM_STR,
            )

            builder.records.stringin(
                f"{enumerated_bits_prefix}:NAME",
                VAL=label,
                DESC="Name of field connected to this BIT",
            )

        # PVI TODO: Not sure how to represent these ones

        return record_dict

    def _make_bit_mux(
        self,
        record_name: EpicsName,
        field_info: FieldInfo,
        values: dict[EpicsName, ScalarRecordValue],
    ) -> dict[EpicsName, RecordInfo]:
        self._check_num_values(values, 2)
        assert isinstance(field_info, BitMuxFieldInfo)
        record_dict: dict[EpicsName, RecordInfo] = {}

        # This should be an mbbOut record, but there are too many posssible labels
        # TODO: There will need to be some mechanism to retrieve the labels,
        # but there's a BITS table that can probably be used
        validator = StringRecordLabelValidator(field_info.labels)
        # Ensure we're putting a valid value to start with
        assert values[record_name] in field_info.labels

        record_dict[record_name] = self._create_record_info(
            record_name,
            field_info.description,
            builder.stringOut,
            str,
            PviGroup.INPUTS,
            initial_value=values[record_name],
            validate=validator.validate,
        )

        delay_record_name = EpicsName(record_name + ":DELAY")
        record_dict[delay_record_name] = self._create_record_info(
            delay_record_name,
            "Clock delay on input",
            builder.longOut,
            int,
            PviGroup.INPUTS,
            initial_value=values[delay_record_name],
        )

        record_dict[delay_record_name].record.DRVH = field_info.max_delay
        record_dict[delay_record_name].record.DRVL = 0

        return record_dict

    def _make_pos_mux(
        self,
        record_name: EpicsName,
        field_info: FieldInfo,
        values: dict[EpicsName, ScalarRecordValue],
    ) -> dict[EpicsName, RecordInfo]:
        self._check_num_values(values, 1)
        assert isinstance(field_info, PosMuxFieldInfo)

        record_dict: dict[EpicsName, RecordInfo] = {}

        # This should be an mbbOut record, but there are too many posssible labels
        # TODO: There will need to be some mechanism to retrieve the labels,
        # but there's a POSITIONS table that can probably be used.
        # OR PVAccess somehow?
        validator = StringRecordLabelValidator(field_info.labels)
        # Ensure we're putting a valid value to start with
        assert values[record_name] in field_info.labels

        record_dict[record_name] = self._create_record_info(
            record_name,
            field_info.description,
            builder.stringOut,
            str,
            PviGroup.INPUTS,
            initial_value=values[record_name],
            validate=validator.validate,
        )

        return record_dict

    def _make_table(
        self,
        record_name: EpicsName,
        field_info: FieldInfo,
        values: dict[EpicsName, list[str]],
    ) -> dict[EpicsName, RecordInfo]:
        assert isinstance(field_info, TableFieldInfo)

        table_updater = TableUpdater(
            self._client,
            record_name,
            field_info,
            self._all_values_dict,
        )

        # Format the mode record name to remove namespace
        mode_record_name: str = table_updater.mode_record_info.record.name
        mode_record_name = EpicsName(
            mode_record_name.replace(self._record_prefix + ":", "")
        )

        return {mode_record_name: table_updater.mode_record_info}

    def _make_uint(
        self,
        record_name: EpicsName,
        field_info: FieldInfo,
        record_creation_func: Callable,
        group: PviGroup,
        **kwargs,
    ) -> dict[EpicsName, RecordInfo]:
        assert isinstance(field_info, UintFieldInfo)

        record_dict: dict[EpicsName, RecordInfo] = {}
        record_dict[record_name] = self._create_record_info(
            record_name,
            field_info.description,
            record_creation_func,
            int,
            group,
            **kwargs,
        )
        max_val = field_info.max_val

        if record_creation_func in OUT_RECORD_FUNCTIONS:
            record_dict[record_name].record.DRVL = 0
            record_dict[record_name].record.DRVH = max_val

        record_dict[record_name].record.HOPR = max_val

        return record_dict

    def _make_uint_param(
        self,
        record_name: EpicsName,
        field_info: FieldInfo,
        values: dict[EpicsName, ScalarRecordValue],
    ) -> dict[EpicsName, RecordInfo]:
        self._check_num_values(values, 1)
        return self._make_uint(
            record_name,
            field_info,
            builder.aOut,
            PviGroup.PARAMETERS,
            initial_value=values[record_name],
            PREC=0,
        )

    def _make_uint_read(
        self,
        record_name: EpicsName,
        field_info: FieldInfo,
        values: dict[EpicsName, ScalarRecordValue],
    ) -> dict[EpicsName, RecordInfo]:
        self._check_num_values(values, 1)
        return self._make_uint(
            record_name,
            field_info,
            builder.aIn,
            PviGroup.READBACKS,
            initial_value=values[record_name],
            PREC=0,
        )

    def _make_uint_write(
        self,
        record_name: EpicsName,
        field_info: FieldInfo,
        values: dict[EpicsName, ScalarRecordValue],
    ) -> dict[EpicsName, RecordInfo]:
        self._check_num_values(values, 0)
        return self._make_uint(
            record_name,
            field_info,
            builder.aOut,
            PviGroup.OUTPUTS,  # TODO: Is this right? No examples to follow
            always_update=True,
            PREC=0,
        )

    # TODO: Why don't I have a _make_int()? I do for other similar types
    def _make_int_param(
        self,
        record_name: EpicsName,
        field_info: FieldInfo,
        values: dict[EpicsName, ScalarRecordValue],
    ) -> dict[EpicsName, RecordInfo]:
        self._check_num_values(values, 1)

        return {
            record_name: self._create_record_info(
                record_name,
                field_info.description,
                builder.longOut,
                int,
                PviGroup.PARAMETERS,
                initial_value=values[record_name],
            )
        }

    def _make_int_read(
        self,
        record_name: EpicsName,
        field_info: FieldInfo,
        values: dict[EpicsName, ScalarRecordValue],
    ) -> dict[EpicsName, RecordInfo]:
        self._check_num_values(values, 1)

        return {
            record_name: self._create_record_info(
                record_name,
                field_info.description,
                builder.longIn,
                int,
                PviGroup.READBACKS,
                initial_value=values[record_name],
            )
        }

    def _make_int_write(
        self,
        record_name: EpicsName,
        field_info: FieldInfo,
        values: dict[EpicsName, ScalarRecordValue],
    ) -> dict[EpicsName, RecordInfo]:
        self._check_num_values(values, 0)
        return {
            record_name: self._create_record_info(
                record_name,
                field_info.description,
                builder.longOut,
                int,
                PviGroup.PARAMETERS,
                always_update=True,
            )
        }

    def _make_scalar(
        self,
        record_name: EpicsName,
        field_info: FieldInfo,
        record_creation_func: Callable,
        **kwargs,
    ) -> dict[EpicsName, RecordInfo]:
        # RAW attribute ignored - EPICS should never care about it
        assert isinstance(field_info, ScalarFieldInfo)
        record_dict: dict[EpicsName, RecordInfo] = {}

        record_dict[record_name] = self._create_record_info(
            record_name,
            field_info.description,
            record_creation_func,
            float,
            PviGroup.READBACKS,
            EGU=field_info.units,
            **kwargs,
        )

        return record_dict

    def _make_scalar_param(
        self,
        record_name: EpicsName,
        field_info: FieldInfo,
        values: dict[EpicsName, ScalarRecordValue],
    ) -> dict[EpicsName, RecordInfo]:
        self._check_num_values(values, 1)
        return self._make_scalar(
            record_name,
            field_info,
            builder.aOut,
            initial_value=values[record_name],
        )

    def _make_scalar_read(
        self,
        record_name: EpicsName,
        field_info: FieldInfo,
        values: dict[EpicsName, ScalarRecordValue],
    ) -> dict[EpicsName, RecordInfo]:
        self._check_num_values(values, 1)
        return self._make_scalar(
            record_name,
            field_info,
            builder.aIn,
            initial_value=values[record_name],
        )

    def _make_scalar_write(
        self,
        record_name: EpicsName,
        field_info: FieldInfo,
        values: dict[EpicsName, ScalarRecordValue],
    ) -> dict[EpicsName, RecordInfo]:
        self._check_num_values(values, 0)
        return self._make_scalar(
            record_name, field_info, builder.aOut, always_update=True
        )

    def _make_bit(
        self,
        record_name: EpicsName,
        field_info: FieldInfo,
        record_creation_func: Callable,
        group: PviGroup,
        **kwargs,
    ) -> dict[EpicsName, RecordInfo]:
        return {
            record_name: self._create_record_info(
                record_name,
                field_info.description,
                record_creation_func,
                int,
                group,
                ZNAM=ZNAM_STR,
                ONAM=ONAM_STR,
                **kwargs,
            )
        }

    def _make_bit_param(
        self,
        record_name: EpicsName,
        field_info: FieldInfo,
        values: dict[EpicsName, ScalarRecordValue],
    ) -> dict[EpicsName, RecordInfo]:
        self._check_num_values(values, 1)
        return self._make_bit(
            record_name,
            field_info,
            builder.boolOut,
            PviGroup.PARAMETERS,
            initial_value=values[record_name],
        )

    def _make_bit_read(
        self,
        record_name: EpicsName,
        field_info: FieldInfo,
        values: dict[EpicsName, ScalarRecordValue],
    ) -> dict[EpicsName, RecordInfo]:
        self._check_num_values(values, 1)
        return self._make_bit(
            record_name,
            field_info,
            builder.boolIn,
            PviGroup.READBACKS,
            initial_value=values[record_name],
        )

    def _make_bit_write(
        self,
        record_name: EpicsName,
        field_info: FieldInfo,
        values: dict[EpicsName, ScalarRecordValue],
    ) -> dict[EpicsName, RecordInfo]:
        self._check_num_values(values, 0)
        return self._make_bit(
            record_name,
            field_info,
            builder.boolOut,
            PviGroup.OUTPUTS,  # TODO: Is this right? No examples to follow
            always_update=True,
        )

    def _make_action_read(
        self,
        record_name: EpicsName,
        field_info: FieldInfo,
        values: dict[EpicsName, ScalarRecordValue],
    ) -> dict[EpicsName, RecordInfo]:
        logging.warning(
            f"Field of type {field_info.type} - {field_info.subtype} defined. Ignoring."
        )
        return {}

    def _make_action_write(
        self,
        record_name: EpicsName,
        field_info: FieldInfo,
        values: dict[EpicsName, ScalarRecordValue],
    ) -> dict[EpicsName, RecordInfo]:
        self._check_num_values(values, 0)

        updater: _WriteRecordUpdater

        record_info = self._create_record_info(
            record_name,
            field_info.description,
            builder.Action,
            int,  # not bool, as that'll treat string "0" as true
            PviGroup.OUTPUTS,  # TODO: Not sure what group to use
            ZNAM="",
            ONAM="",
            on_update=lambda v: updater.update(v),
        )

        updater = _WriteRecordUpdater(
            record_info, self._record_prefix, self._client, self._all_values_dict, None
        )

        record_info.add_record(record_info.record)

        return {record_name: record_info}

    def _make_lut(
        self,
        record_name: EpicsName,
        field_info: FieldInfo,
        record_creation_func: Callable,
        group: PviGroup,
        **kwargs,
    ) -> dict[EpicsName, RecordInfo]:
        # RAW attribute ignored - EPICS should never care about it
        return {
            record_name: self._create_record_info(
                record_name,
                field_info.description,
                record_creation_func,
                str,
                group,
                **kwargs,
            ),
        }

    def _make_lut_param(
        self,
        record_name: EpicsName,
        field_info: FieldInfo,
        values: dict[EpicsName, ScalarRecordValue],
    ) -> dict[EpicsName, RecordInfo]:
        self._check_num_values(values, 1)
        return self._make_lut(
            record_name,
            field_info,
            builder.stringOut,
            PviGroup.PARAMETERS,
            initial_value=values[record_name],
        )

    def _make_lut_read(
        self,
        record_name: EpicsName,
        field_info: FieldInfo,
        values: dict[EpicsName, ScalarRecordValue],
    ) -> dict[EpicsName, RecordInfo]:
        self._check_num_values(values, 1)
        return self._make_lut(
            record_name,
            field_info,
            builder.stringIn,
            PviGroup.READBACKS,  # TODO: Is this right? No examples to follow
            initial_value=values[record_name],
        )

    def _make_lut_write(
        self,
        record_name: EpicsName,
        field_info: FieldInfo,
        values: dict[EpicsName, ScalarRecordValue],
    ) -> dict[EpicsName, RecordInfo]:
        self._check_num_values(values, 0)
        return self._make_lut(
            record_name,
            field_info,
            builder.stringOut,
            PviGroup.OUTPUTS,  # TODO: Is this right? No examples to follow
            always_update=True,
        )

    def _make_enum(
        self,
        record_name: EpicsName,
        field_info: FieldInfo,
        values: dict[EpicsName, ScalarRecordValue],
        record_creation_func: Callable,
        group: PviGroup,
        **kwargs,
    ) -> dict[EpicsName, RecordInfo]:
        self._check_num_values(values, 1)
        assert isinstance(field_info, EnumFieldInfo)

        labels, index_value = self._process_labels(
            field_info.labels, values[record_name]
        )

        return {
            record_name: self._create_record_info(
                record_name,
                field_info.description,
                record_creation_func,
                int,
                group,
                labels=labels,
                initial_value=index_value,
                **kwargs,
            )
        }

    def _make_enum_param(
        self,
        record_name: EpicsName,
        field_info: FieldInfo,
        values: dict[EpicsName, ScalarRecordValue],
    ) -> dict[EpicsName, RecordInfo]:
        return self._make_enum(
            record_name, field_info, values, builder.mbbOut, PviGroup.PARAMETERS
        )

    def _make_enum_read(
        self,
        record_name: EpicsName,
        field_info: FieldInfo,
        values: dict[EpicsName, ScalarRecordValue],
    ) -> dict[EpicsName, RecordInfo]:
        # Don't use an mbbIn record, as many labels are too long to fit into EPICS
        # restricted-length labels. As you cannot write to this record, it's fine to
        # just have a string
        return {
            # TODO: Determining the PviGroup here is VERY fragile
            record_name: self._create_record_info(
                record_name,
                field_info.description,
                builder.stringIn,
                str,
                PviGroup.NONE if record_name.endswith("HEALTH") else PviGroup.READBACKS,
                initial_value=values[record_name],
            )
        }

    def _make_enum_write(
        self,
        record_name: EpicsName,
        field_info: FieldInfo,
        values: dict[EpicsName, ScalarRecordValue],
    ) -> dict[EpicsName, RecordInfo]:
        assert isinstance(field_info, EnumFieldInfo)
        assert record_name not in values
        # Values are not returned for write fields. Create data for label parsing.
        values = {record_name: field_info.labels[0]}
        return self._make_enum(
            record_name,
            field_info,
            values,
            builder.mbbOut,
            PviGroup.OUTPUTS,  # TODO: Is this right? No examples to follow
            always_update=True,
        )

    def create_record(
        self,
        record_name: EpicsName,
        field_info: FieldInfo,
        field_values: dict[EpicsName, RecordValue],
    ) -> dict[EpicsName, RecordInfo]:
        # TODO: Name needs changing, this makes multiple records...
        """Create the record (and any child records) for the PandA field specified in
        the parameters.

        Args:
            record_name: The name of the record to create, with colons separating
                words in EPICS style.
            field_info: The field info for the record being created
            field_values: The dictionary of values for the record and
                all child records. The keys are in EPICS style.

        Returns:
            Dict[str, RecordInfo]: A dictionary of created RecordInfo objects that
                will need updating later. Not all created records are returned.
        """

        try:
            key = (field_info.type, field_info.subtype)
            if key == ("table", None):
                # Table expects vals in Dict[str, List[str]]
                list_vals = {
                    EpicsName(k): v
                    for (k, v) in field_values.items()
                    if isinstance(v, list)
                }

                return self._make_table(record_name, field_info, list_vals)

            # PandA can never report a table field as in error, only scalar fields
            str_vals = {
                EpicsName(k): v
                for (k, v) in field_values.items()
                if isinstance(v, (str, InErrorException))
            }

            return self._field_record_mapping[key](
                self, record_name, field_info, str_vals
            )

        except KeyError:
            # Unrecognised type-subtype key, ignore this item. This allows the server
            # to define new types without breaking the client.
            logging.exception(
                f"Unrecognised type {key} while processing record {record_name}"
            )
            return {}

    # Map a field's (type, subtype) to a function that creates and returns record(s)
    _field_record_mapping: dict[
        tuple[str, Optional[str]],
        Callable[
            [
                "IocRecordFactory",
                EpicsName,
                FieldInfo,
                dict[EpicsName, ScalarRecordValue],
            ],
            dict[EpicsName, RecordInfo],
        ],
    ] = {
        # Order matches that of PandA server's Field Types docs
        ("time", None): _make_type_time,
        ("bit_out", None): _make_bit_out,
        ("pos_out", None): _make_pos_out,
        ("ext_out", "timestamp"): _make_ext_out,
        ("ext_out", "samples"): _make_ext_out,
        ("ext_out", "bits"): _make_ext_out_bits,
        ("bit_mux", None): _make_bit_mux,
        ("pos_mux", None): _make_pos_mux,
        # ("table", None): _make_table, TABLE handled separately
        ("param", "uint"): _make_uint_param,
        ("read", "uint"): _make_uint_read,
        ("write", "uint"): _make_uint_write,
        ("param", "int"): _make_int_param,
        ("read", "int"): _make_int_read,
        ("write", "int"): _make_int_write,
        ("param", "scalar"): _make_scalar_param,
        ("read", "scalar"): _make_scalar_read,
        ("write", "scalar"): _make_scalar_write,
        ("param", "bit"): _make_bit_param,
        ("read", "bit"): _make_bit_read,
        ("write", "bit"): _make_bit_write,
        ("param", "action"): _make_action_read,
        ("read", "action"): _make_action_read,
        ("write", "action"): _make_action_write,
        ("param", "lut"): _make_lut_param,
        ("read", "lut"): _make_lut_read,
        ("write", "lut"): _make_lut_write,
        ("param", "enum"): _make_enum_param,
        ("read", "enum"): _make_enum_read,
        ("write", "enum"): _make_enum_write,
        ("param", "time"): _make_subtype_time_param,
        ("read", "time"): _make_subtype_time_read,
        ("write", "time"): _make_subtype_time_write,
    }

    async def _arm_on_update(self, new_val: int) -> None:
        """Process an update to the Arm record, to arm/disarm the PandA"""
        logging.debug(f"Entering HDF5:Arm record on_update method, value {new_val}")
        try:
            if new_val:
                logging.info("Arming PandA")
                await self._client.send(Arm())
            else:
                logging.info("Disarming PandA")
                await self._client.send(Disarm())

        except Exception:
            logging.exception("Failure arming/disarming PandA")

    def create_block_records(
        self,
        block: str,
        block_info: BlockInfo,
        block_values: dict[EpicsName, str],
        default_longStringOut_length=256,
    ) -> dict[EpicsName, RecordInfo]:
        """Create the block-level records, and any other one-off block initialisation
        required."""

        record_dict = {}
        for key, value in block_values.items():
            # LABEL will either get its value from the block_values if present,
            # or fall back to the block_info description field.
            if (value == "" or value is None) and block_info.description:
                value = block_info.description

            # The record uses the default _RecordUpdater.update to update the value
            # on the panda
            record_dict[EpicsName(key)] = self._create_record_info(
                key,
                None,
                builder.longStringOut,
                str,
                PviGroup.INPUTS,
                length=default_longStringOut_length,
                initial_value=value,
            )

        if block == "PCAP":
            # TODO: Need to add PVI Info here. Just use create_record_info?
            # And why isn't this record in the record_dict?

            pcap_arm_record = builder.Action(
                "PCAP:ARM",
                ZNAM="Disarm",
                ONAM="Arm",
                on_update=self._arm_on_update,
                DESC="Arm/Disarm the PandA",
            )

            add_pcap_arm_pvi_info(PviGroup.INPUTS, pcap_arm_record)

            HDF5RecordController(
                self._client,
                self._dataset_cache,
                self._record_prefix,
            )

        return record_dict

    def create_version_records(self, firmware_versions: dict[EpicsName, str]):
        """Creates handful of records for tracking versions of IOC/Firmware via EPICS

        Args:
            firmware_versions (dict[str, str]): Dictionary mapping firmwares to versions
        """

        system_block_prefix = "SYSTEM"

        ioc_version_record_name = EpicsName(system_block_prefix + ":IOC_VERSION")
        ioc_version_record = builder.stringIn(
            ioc_version_record_name, DESC="IOC Version", initial_value=__version__
        )
        add_automatic_pvi_info(
            PviGroup.VERSIONS,
            ioc_version_record,
            ioc_version_record_name,
            builder.stringIn,
        )

        for firmware_name, version in firmware_versions.items():
            firmware_record_name = EpicsName(
                system_block_prefix + f":{firmware_name}_VERSION"
            )
            firmware_ver_record = builder.stringIn(
                firmware_record_name, DESC=firmware_name, initial_value=version
            )
            add_automatic_pvi_info(
                PviGroup.VERSIONS,
                firmware_ver_record,
                firmware_record_name,
                builder.stringIn,
            )

    def initialise(self, dispatcher: asyncio_dispatcher.AsyncioDispatcher) -> None:
        """Perform any final initialisation code to create the records. No new
        records may be created after this method is called.

        Args:
            dispatcher (asyncio_dispatcher.AsyncioDispatcher): The dispatcher used in
                IOC initialisation
        """
        builder.LoadDatabase()
        softioc.iocInit(dispatcher)


async def create_records(
    client: AsyncioClient,
    dispatcher: asyncio_dispatcher.AsyncioDispatcher,
    record_prefix: str,
) -> tuple[
    dict[EpicsName, RecordInfo],
    dict[
        EpicsName,
        RecordValue,
    ],
    dict[str, BlockInfo],
]:
    """Query the PandA and create the relevant records based on the information
    returned"""

    # Get version information from PandA using IDN command
    idn_response = await client.send(Get("*IDN"))
    fw_vers_dict = get_panda_versions(idn_response)

    (panda_dict, all_values_dict) = await introspect_panda(client)

    # Dictionary containing every record of every type
    all_records: dict[EpicsName, RecordInfo] = {}

    record_factory = IocRecordFactory(client, record_prefix, all_values_dict)

    # Add records for version of IOC, FPGA, and software to SYSTEM block
    record_factory.create_version_records(fw_vers_dict)

    # For each field in each block, create block_num records of each field
    for block, panda_info in panda_dict.items():
        block_info = panda_info.block_info
        values = panda_info.values

        block_vals = {
            key: value
            for key, value in values.items()
            if key.endswith(":LABEL") and isinstance(value, str)
        }

        # Create block-level records
        block_records = record_factory.create_block_records(
            block, block_info, block_vals
        )

        for new_record in block_records:
            if new_record in all_records:
                raise Exception(f"Duplicate record name {new_record} detected.")

        for block_num in range(block_info.number):
            # Add a suffix if there are multiple of a block e.g:
            # "SEQ:TABLE" -> "SEQ3:TABLE"
            # Block numbers are indexed from 1
            suffixed_block = block
            if block_info.number > 1:
                suffixed_block += str(block_num + 1)

            for field, field_info in panda_info.fields.items():
                # ":" separator for EPICS Record names, unlike PandA's "."
                record_name = EpicsName(suffixed_block + ":" + field)

                # Get the value of the field and all its sub-fields
                # Watch for cases where the record name is a prefix to multiple
                # unrelated fields. e.g. for record_name "INENC1:CLK",
                # values for keys "INENC1:CLK" "INENC1:CLK:DELAY" should match
                # but "INENC1:CLK_PERIOD" should not

                field_values = {
                    field: value
                    for field, value in values.items()
                    if field == record_name or field.startswith(record_name + ":")
                }

                records = record_factory.create_record(
                    record_name, field_info, field_values
                )

                for new_record in records:
                    if new_record in all_records:
                        raise Exception(f"Duplicate record name {new_record} detected.")

                for record_info in records.values():
                    record_info._field_info = field_info

                block_records.update(records)

        all_records.update(block_records)

    Pvi.create_pvi_records(record_prefix)

    record_factory.initialise(dispatcher)

    block_info_dict = {key: value.block_info for key, value in panda_dict.items()}
    return (all_records, all_values_dict, block_info_dict)


async def update(
    client: AsyncioClient,
    connection_status: ConnectionStatus,
    all_records: dict[EpicsName, RecordInfo],
    poll_period: float,
    all_values_dict: dict[EpicsName, RecordValue],
    block_info_dict: dict[str, BlockInfo],
):
    """Query the PandA at regular intervals for any changed fields, and update
    the records accordingly

    Args:
        client: The AsyncioClient that will be used to get the Changes from the PandA
        all_records: The dictionary of all records that are expected to be updated when
            PandA reports changes. This is NOT all records in the IOC.
        poll_period: The wait time, in seconds, before the next GetChanges is called.
        all_values_dict: The dictionary containing the most recent value of all records
            as returned from GetChanges. This method will update values in the dict,
            which will be read and used in other places
        block_info: information recieved from the last `GetBlockInfo`, keys are block
            names"""

    fields_to_reset: list[tuple[RecordWrapper, Any]] = []

    # Fairly arbitrary choice of timeout time
    timeout = 10 * poll_period

    while True:
        try:
            for record, value in fields_to_reset:
                record.set(value)
                fields_to_reset.remove((record, value))

            try:
                changes = await client.send(GetChanges(ChangeGroup.ALL, True), timeout)
            except asyncio.TimeoutError:
                # Indicates PandA did not reply within the timeout
                logging.error(
                    f"PandA did not respond to GetChanges within {timeout} seconds. "
                    "Setting all records to major alarm state and disconnecting."
                )
                connection_status.set_status(Statuses.DISCONNECTED)
                set_all_records_severity(
                    all_records, alarm.MAJOR_ALARM, alarm.READ_ACCESS_ALARM
                )
                await client.close()
                break

            _, new_all_values_dict = _create_dicts_from_changes(
                changes, block_info_dict
            )

            # Apply the new values to the existing dict, so various updater classes
            # will have access to the latest values.
            # As this is the only place we write to this dict (after initial creation),
            # we don't need to worry about locking accesses - the GIL will enforce it
            all_values_dict.update(new_all_values_dict)

            for field in changes.in_error:
                field = PandAName(field)
                field = panda_to_epics_name(field)

                if field not in all_records:
                    logging.error(
                        f"Unknown field {field} returned from GetChanges in_error"
                    )
                    continue

                logging.info(f"Setting record {field} to invalid value error state.")
                record_info: RecordInfo = all_records[field]
                # See PythonSoftIOC #53
                if record_info.is_in_record:
                    record_info.record.set_alarm(alarm.INVALID_ALARM, alarm.UDF_ALARM)
                else:
                    logging.warning(
                        f"Cannot set error state for record {record_info.record.name}"
                    )

            for field, value in changes.values.items():
                field = PandAName(field)
                field = panda_to_epics_name(field)

                if block_label := extract_label_from_metadata(
                    *field.split(":", maxsplit=1)
                ):
                    block_label_no_number = re.sub(r"\d*$", "", block_label)
                    block_label = f"{block_label}:LABEL"
                    block_label_no_number = f"{block_label_no_number}:LABEL"

                    if block_label_no_number in all_records:
                        field = block_label_no_number
                    elif block_label in all_records:
                        field = block_label

                if field not in all_records:
                    logging.error(
                        f"Unknown field {field} returned from GetChanges values"
                    )
                    continue

                record_info = all_records[field]
                record = record_info.record

                # Note bit_mux/pos_mux fields probably should have labels in their
                # RecordInfo, but that would break this code. This is only designed
                # for mbbi/mbbo records.
                converted_value = (
                    record_info.labels.index(value)
                    if record_info.labels
                    else record_info.data_type_func(value)
                )

                try:
                    if record_info._pending_change:
                        record_info._pending_change = False
                        if converted_value == record_info.record.get():
                            # This is most likely PandA reporting a value we just Put
                            continue

                    if (
                        record_info._field_info
                        and record_info._field_info.type == "bit_out"
                    ):
                        # Its possible a bit_out field will be on for pulses shorter
                        # than our polling time. To represent this we will invert the
                        # value now, then set it back on the next update
                        if converted_value == record_info.record.get():
                            fields_to_reset.append(
                                (record_info.record, converted_value)
                            )
                            converted_value = not converted_value

                    # Do not process, as the on_update methods push data back to PandA.
                    # Any processing that must be done at value update must be handled
                    # through record_info.on_changes_func()
                    if record_info.on_changes_func:
                        await record_info.on_changes_func(value)

                    extra_kwargs = {}
                    if not record_info.is_in_record:
                        extra_kwargs.update({"process": False})

                    record.set(converted_value, **extra_kwargs)
                except Exception:
                    logging.exception(
                        f"Exception setting record {record.name} to new value {value}"
                    )
            for table_field, value_list in changes.multiline_values.items():
                table_field = PandAName(table_field)
                table_field = panda_to_epics_name(table_field)
                # Tables must have a MODE record defined - use it to update the table
                mode_record_name = EpicsName(table_field + ":MODE")
                if mode_record_name not in all_records:
                    logging.error(
                        f"Table MODE record {mode_record_name} not found."
                        f" Skipping update to table {table_field}"
                    )

                    continue

                mode_record = all_records[mode_record_name].record
                assert isinstance(mode_record, TableRecordWrapper)
                mode_record.update_table(value_list)

            await asyncio.sleep(poll_period)
        # Only here for testing purposes
        except asyncio.CancelledError:
            break
        except Exception:
            logging.exception("Exception while processing updates from PandA")
            continue


def set_all_records_severity(
    all_records: dict[EpicsName, RecordInfo], severity: int, alarm: int
):
    """Set the severity of all possible records to the given state"""
    logging.debug(f"Setting all record to severity {severity} alarm {alarm}")
    for record_info in all_records.values():
        if record_info.is_in_record:
            record_info.record.set_alarm(severity, alarm)
