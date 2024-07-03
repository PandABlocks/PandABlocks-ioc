import asyncio
import typing
from typing import Dict, List
from unittest.mock import AsyncMock

import numpy
import numpy.testing
import pytest
from aioca import caget, camonitor, caput
from mock.mock import MagicMock, PropertyMock
from numpy import ndarray
from pandablocks.asyncio import AsyncioClient
from pandablocks.commands import GetMultiline, Put
from pandablocks.responses import TableFieldDetails, TableFieldInfo
from pandablocks.utils import words_to_table
from softioc import alarm

from fixtures.mocked_panda import TIMEOUT, command_to_key, multiprocessing_queue_to_list
from pandablocks_ioc._tables import (
    TableFieldRecordContainer,
    TableModeEnum,
    TableUpdater,
)
from pandablocks_ioc._types import EpicsName, InErrorException, RecordInfo, RecordValue

PANDA_FORMAT_TABLE_NAME = "SEQ1.TABLE"
EPICS_FORMAT_TABLE_NAME = "SEQ1:TABLE"


@pytest.fixture
def table_data_1_dict(table_data_1: List[str]) -> Dict[EpicsName, RecordValue]:
    return {EpicsName(EPICS_FORMAT_TABLE_NAME): table_data_1}


@pytest.fixture
def table_fields_records(
    table_fields: Dict[str, TableFieldDetails],
    table_unpacked_data: typing.OrderedDict[EpicsName, ndarray],
) -> Dict[str, TableFieldRecordContainer]:
    """A faked list of records containing the table_unpacked_data"""

    data = {}
    for (field_name, field_info), data_array in zip(
        table_fields.items(), table_unpacked_data.values()
    ):
        mocked_record = MagicMock()
        type(mocked_record).name = PropertyMock(
            return_value=EPICS_FORMAT_TABLE_NAME + ":" + field_name
        )
        mocked_record.get = MagicMock(return_value=data_array)
        record_info = RecordInfo(lambda x: None)
        record_info.add_record(mocked_record)
        data[field_name] = TableFieldRecordContainer(field_info, record_info)
    return data


@pytest.fixture
def table_updater(
    table_field_info: TableFieldInfo,
    table_data_1_dict: Dict[EpicsName, RecordValue],
    clear_records,
    table_unpacked_data: typing.OrderedDict[EpicsName, ndarray],
) -> TableUpdater:
    """Provides a TableUpdater with configured records and mocked functionality"""
    client = AsyncioClient("123")
    client.send = AsyncMock()  # type: ignore
    # mypy doesn't play well with mocking so suppress error

    mocked_mode_record = MagicMock()
    # Default mode record to VIEW, as per default construction
    mocked_mode_record.get = MagicMock(return_value=TableModeEnum.VIEW.value)
    mocked_mode_record.set = MagicMock()
    mode_record_info = RecordInfo(
        lambda x: None,
        labels=[
            TableModeEnum.VIEW.name,
            TableModeEnum.EDIT.name,
            TableModeEnum.SUBMIT.name,
            TableModeEnum.DISCARD.name,
        ],
    )
    mode_record_info.add_record(mocked_mode_record)

    updater = TableUpdater(
        client,
        EpicsName(EPICS_FORMAT_TABLE_NAME),
        table_field_info,
        table_data_1_dict,
    )

    # Put mocks into TableUpdater
    updater.mode_record_info = mode_record_info
    for field_name, table_record_container in updater.table_fields_records.items():
        assert table_record_container.record_info
        table_record_container.record_info.record = MagicMock()
        type(table_record_container.record_info.record).name = PropertyMock(
            return_value=EPICS_FORMAT_TABLE_NAME + ":" + field_name
        )
        table_record_container.record_info.record.get = MagicMock(
            return_value=table_unpacked_data[EpicsName(field_name)]
        )

    return updater


async def test_create_softioc_update_table(
    mocked_panda_standard_responses,
    table_unpacked_data,
):
    """Test that the update mechanism correctly changes table values when PandA
    reports values have changed"""

    (
        tmp_path,
        child_conn,
        response_handler,
        command_queue,
        test_prefix,
    ) = mocked_panda_standard_responses

    try:
        # Set up a monitor to wait for the expected change
        capturing_queue = asyncio.Queue()
        monitor = camonitor(test_prefix + ":SEQ:TABLE:TIME1", capturing_queue.put)

        curr_val = await asyncio.wait_for(capturing_queue.get(), TIMEOUT)
        # First response is the current value
        numpy.testing.assert_array_equal(curr_val, table_unpacked_data["TIME1"])

        # Wait for the new value to appear
        curr_val = await asyncio.wait_for(capturing_queue.get(), TIMEOUT)
        assert numpy.array_equal(
            curr_val,
            [100, 0, 9, 5, 99999],
        )

        # And check some other columns too
        curr_val = await caget(test_prefix + ":SEQ:TABLE:TRIGGER")
        #
        assert numpy.array_equal(
            curr_val,
            numpy.array(
                [
                    "Immediate",
                    "Immediate",
                    "Immediate",
                    "POSB>=POSITION",
                    "POSC<=POSITION",
                ],
            ),
        )

        curr_val = await caget(test_prefix + ":SEQ:TABLE:POSITION")
        assert numpy.array_equal(curr_val, [-5, 0, 0, 444444, -99])

        curr_val = await caget(test_prefix + ":SEQ:TABLE:OUTD2")
        assert numpy.array_equal(curr_val, [0, 0, 1, 1, 0])

    finally:
        monitor.close()


async def test_create_softioc_table_update_send_to_panda(
    mocked_panda_standard_responses,
):
    """Test that updating a table causes the new value to be sent to PandA"""

    (
        tmp_path,
        child_conn,
        response_handler,
        command_queue,
        test_prefix,
    ) = mocked_panda_standard_responses
    try:
        trig_queue = asyncio.Queue()
        m1 = camonitor(test_prefix + ":PCAP:TRIG_EDGE", trig_queue.put, datatype=str)

        # Wait for all the dummy changes to finish
        assert await asyncio.wait_for(trig_queue.get(), TIMEOUT) == "Falling"
        assert await asyncio.wait_for(trig_queue.get(), TIMEOUT) == "Either"

    finally:
        m1.close()

    await caput(test_prefix + ":SEQ:TABLE:MODE", "EDIT", wait=True, timeout=TIMEOUT)

    await caput(
        test_prefix + ":SEQ:TABLE:REPEATS", [1, 1, 1, 1, 1], wait=True, timeout=TIMEOUT
    )

    await caput(test_prefix + ":SEQ:TABLE:MODE", "SUBMIT", wait=True, timeout=TIMEOUT)

    # Give the queue time to be put to
    await asyncio.sleep(0.1)

    commands_recieved_by_panda = multiprocessing_queue_to_list(command_queue)

    assert (
        command_to_key(
            Put(
                field="SEQ.TABLE",
                value=[
                    "2457862145",
                    "4294967291",
                    "100",
                    "0",
                    "1",
                    "0",
                    "0",
                    "0",
                    "4293918721",
                    "0",
                    "9",
                    "9999",
                    "2035875841",
                    "444444",
                    "5",
                    "1",
                    "3464232961",
                    "4294967197",
                    "99999",
                    "2222",
                ],
            )
        )
        in commands_recieved_by_panda
    )


def test_table_updater_validate_mode_view(table_updater: TableUpdater):
    """Test the validate method when mode is View"""

    # View is default in table_updater
    record = MagicMock()
    record.name = MagicMock(return_value="NewRecord")
    assert table_updater.validate_waveform(record, "value is irrelevant") is False


def test_table_updater_validate_mode_edit(table_updater: TableUpdater):
    """Test the validate method when mode is Edit"""

    table_updater.mode_record_info.record.get = MagicMock(
        return_value=TableModeEnum.EDIT.value
    )

    record = MagicMock()
    record.name = MagicMock(return_value="NewRecord")
    assert table_updater.validate_waveform(record, "value is irrelevant") is True


def test_table_updater_validate_mode_submit(table_updater: TableUpdater):
    """Test the validate method when mode is Submit"""

    table_updater.mode_record_info.record.get = MagicMock(
        return_value=TableModeEnum.SUBMIT.value
    )

    record = MagicMock()
    record.name = MagicMock(return_value="NewRecord")
    assert table_updater.validate_waveform(record, "value is irrelevant") is False


def test_table_updater_validate_mode_discard(table_updater: TableUpdater):
    """Test the validate method when mode is Discard"""

    table_updater.mode_record_info.record.get = MagicMock(
        return_value=TableModeEnum.DISCARD.value
    )

    record = MagicMock()
    record.name = MagicMock(return_value="NewRecord")
    assert table_updater.validate_waveform(record, "value is irrelevant") is False


def test_table_updater_validate_mode_unknown(table_updater: TableUpdater):
    """Test the validate method when mode is unknown"""

    table_updater.mode_record_info.record.get = MagicMock(
        return_value=12
    )  # Unknown Value
    table_updater.mode_record_info.record.set_alarm = MagicMock()

    record = MagicMock()
    record.name = MagicMock(return_value="NewRecord")

    assert table_updater.validate_waveform(record, "value is irrelevant") is False
    table_updater.mode_record_info.record.set_alarm.assert_called_once_with(
        alarm.INVALID_ALARM, alarm.UDF_ALARM
    )


async def test_table_updater_update_mode_view(table_updater: TableUpdater):
    """Test that update_mode with new value of VIEW takes no action"""
    await table_updater.update_mode(TableModeEnum.VIEW.value)

    assert (
        not table_updater.client.send.called  # type: ignore
    ), "client send method was unexpectedly called"
    assert (
        not table_updater.mode_record_info.record.set.called
    ), "record set method was unexpectedly called"


async def test_table_updater_update_mode_submit(
    table_updater: TableUpdater, table_data_1: List[str]
):
    """Test that update_mode with new value of SUBMIT sends data to PandA"""
    await table_updater.update_mode(TableModeEnum.SUBMIT.value)

    assert isinstance(table_updater.client.send, AsyncMock)
    table_updater.client.send.assert_called_once_with(
        Put(PANDA_FORMAT_TABLE_NAME, table_data_1)
    )

    table_updater.mode_record_info.record.set.assert_called_once_with(
        TableModeEnum.VIEW.value, process=False
    )


async def test_table_updater_update_mode_submit_exception(
    table_updater: TableUpdater,
    table_data_1: List[str],
    table_unpacked_data: typing.OrderedDict[EpicsName, ndarray],
    table_fields: Dict[str, TableFieldDetails],
):
    """Test that update_mode with new value of SUBMIT handles an exception from Put
    correctly"""

    assert isinstance(table_updater.client.send, AsyncMock)
    table_updater.client.send.side_effect = Exception("Mocked exception")

    await table_updater.update_mode(TableModeEnum.SUBMIT.value)

    table_updater.client.send.assert_called_once_with(
        Put(PANDA_FORMAT_TABLE_NAME, table_data_1)
    )

    # Confirm each record received the expected data
    for field_name, data in table_unpacked_data.items():
        # Note table_unpacked_data is deliberately in a different order to the sorted
        # data, hence use this lookup mechanism instead
        record_info = table_updater.table_fields_records[field_name].record_info
        assert record_info
        # numpy arrays don't play nice with mock's equality comparisons, do it ourself
        called_args = record_info.record.set.call_args

        expected = called_args[0][0]

        if table_fields[field_name].labels:
            labels = table_fields[field_name].labels
            expected = numpy.array([labels[x] for x in expected])

        numpy.testing.assert_array_equal(data, expected)

    table_updater.mode_record_info.record.set.assert_called_once_with(
        TableModeEnum.VIEW.value, process=False
    )


async def test_table_updater_update_mode_submit_exception_data_error(
    table_updater: TableUpdater, table_data_1: List[str]
):
    """Test that update_mode with an exception from Put and an InErrorException behaves
    as expected"""
    assert isinstance(table_updater.client.send, AsyncMock)
    table_updater.client.send.side_effect = Exception("Mocked exception")

    table_updater.all_values_dict[EpicsName(EPICS_FORMAT_TABLE_NAME)] = (
        InErrorException("Mocked in error exception")
    )

    await table_updater.update_mode(TableModeEnum.SUBMIT.value)

    for field_record in table_updater.table_fields_records.values():
        assert field_record.record_info
        record = field_record.record_info.record
        record.set.assert_not_called()

    table_updater.client.send.assert_called_once_with(
        Put(PANDA_FORMAT_TABLE_NAME, table_data_1)
    )


async def test_table_updater_update_mode_discard(
    table_updater: TableUpdater,
    table_data_1: List[str],
    table_unpacked_data: typing.OrderedDict[EpicsName, ndarray],
    table_fields: Dict[str, TableFieldDetails],
):
    """Test that update_mode with new value of DISCARD resets record data"""
    assert isinstance(table_updater.client.send, AsyncMock)
    table_updater.client.send.return_value = table_data_1

    await table_updater.update_mode(TableModeEnum.DISCARD.value)

    table_updater.client.send.assert_called_once_with(
        GetMultiline(PANDA_FORMAT_TABLE_NAME)
    )

    # Confirm each record received the expected data
    for field_name, data in table_unpacked_data.items():
        # Note table_unpacked_data is deliberately in a different order to the sorted
        # data, hence use this lookup mechanism instead
        record_info = table_updater.table_fields_records[field_name].record_info
        assert record_info
        # numpy arrays don't play nice with mock's equality comparisons, do it ourself
        called_args = record_info.record.set.call_args

        expected = called_args[0][0]

        if table_fields[field_name].labels:
            labels = table_fields[field_name].labels
            expected = numpy.array([labels[x] for x in expected])

        numpy.testing.assert_array_equal(data, expected)

    table_updater.mode_record_info.record.set.assert_called_once_with(
        TableModeEnum.VIEW.value, process=False
    )


@pytest.mark.parametrize(
    "enum_val", [TableModeEnum.EDIT.value, TableModeEnum.VIEW.value]
)
async def test_table_updater_update_mode_other(
    table_updater: TableUpdater,
    table_unpacked_data: typing.OrderedDict[EpicsName, ndarray],
    enum_val: int,
):
    """Test that update_mode with non-SUBMIT or DISCARD values takes no action"""

    await table_updater.update_mode(enum_val)

    assert isinstance(table_updater.client.send, AsyncMock)
    table_updater.client.send.assert_not_called()

    # Confirm each record was not called
    for field_name, _ in table_unpacked_data.items():
        record_info = table_updater.table_fields_records[field_name].record_info
        assert record_info

        record_info.record.assert_not_called()

    table_updater.mode_record_info.record.set.assert_not_called()


def test_table_updater_update_table(
    table_updater: TableUpdater,
    table_data_1: List[str],
    table_unpacked_data: typing.OrderedDict[EpicsName, ndarray],
):
    """Test that update_table updates records with the new values"""

    table_updater.update_table(table_data_1)

    table_updater.mode_record_info.record.get.assert_called_once()

    # Confirm each record received the expected data
    for field_name, data in table_unpacked_data.items():
        # Note table_unpacked_data is deliberately in a different order to the sorted
        # data, hence use this lookup mechanism instead
        record_info = table_updater.table_fields_records[field_name].record_info
        assert record_info
        # numpy arrays don't play nice with mock's equality comparisons, do it ourself
        called_args = record_info.record.set.call_args

        numpy.testing.assert_array_equal(data, called_args[0][0])


def test_table_updater_update_table_not_view(
    table_updater: TableUpdater,
    table_data_1: List[str],
    table_unpacked_data: typing.OrderedDict[EpicsName, ndarray],
):
    """Test that update_table does nothing when mode is not VIEW"""

    table_updater.mode_record_info.record.get.return_value = TableModeEnum.EDIT

    table_updater.update_table(table_data_1)

    table_updater.mode_record_info.record.get.assert_called_once()

    # Confirm the records were not called
    for field_name, _ in table_unpacked_data.items():
        # Note table_unpacked_data is deliberately in a different order to the sorted
        # data, hence use this lookup mechanism instead
        record_info = table_updater.table_fields_records[field_name].record_info
        assert record_info
        record_info.record.set.assert_not_called()


async def test_table_update_skips_data_sent_from_ioc_once_received_back(
    table_updater: TableUpdater,
    table_data_1: List[str],
):
    """A test that once the ioc sets table values, it won't attempt to
    set the same values once they come back from the panda"""

    await table_updater.update_mode(TableModeEnum.VIEW.value)
    await table_updater.update_mode(TableModeEnum.EDIT.value)
    table_updater.update_table(table_data_1)
    await table_updater.update_mode(TableModeEnum.SUBMIT.value)
    table_updater.update_table(table_data_1)
    assert table_updater._sent_data == table_data_1
    for field_record in table_updater.table_fields_records.values():
        assert isinstance(field_record.record_info, RecordInfo)
        field_record.record_info.record.set.assert_called_once()


async def test_table_update_mode_thread_lock(table_updater):
    async def some_other_mode_update_from_panda():
        with table_updater._mode_lock:
            table_updater._update_in_progress = True
        await asyncio.sleep(0.1)

    async def ioc_update_mode_record():
        # Enough time for the above coroutine to grab the lock
        await asyncio.sleep(0.05)
        assert table_updater._wait_for_mode_lock(None, TableModeEnum.EDIT) is False

    assert table_updater._wait_for_mode_lock(None, TableModeEnum.EDIT) is True
    await asyncio.gather(some_other_mode_update_from_panda(), ioc_update_mode_record())


async def test_table_changed_back_correctly(table_updater, table_data_1, table_data_2):
    table_unpacked_data_1 = words_to_table(
        table_data_1, table_updater.field_info, convert_enum_indices=True
    )
    table_unpacked_data_2 = words_to_table(
        table_data_2, table_updater.field_info, convert_enum_indices=True
    )

    def assert_last_table_data_set_equaled(table_unpacked_data):
        for row, field_record in zip(
            table_unpacked_data.values(), table_updater.table_fields_records.values()
        ):
            assert numpy.array_equal(
                row, field_record.record_info.record.set.call_args[0][-1]
            )

    table_updater.update_table(table_data_1)
    await table_updater.update_mode(TableModeEnum.SUBMIT.value)
    table_updater.update_table(table_data_1)
    assert_last_table_data_set_equaled(table_unpacked_data_1)
    table_updater.update_table(table_data_2)
    assert_last_table_data_set_equaled(table_unpacked_data_2)
    table_updater.update_table(table_data_1)
    assert_last_table_data_set_equaled(table_unpacked_data_1)
