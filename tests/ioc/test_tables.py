from typing import Dict, List

import numpy
import numpy.testing
import pytest
from mock import AsyncMock
from mock.mock import MagicMock, PropertyMock, call
from numpy import array, int32, ndarray, uint8, uint16, uint32
from softioc import alarm

from pandablocks.asyncio import AsyncioClient
from pandablocks.commands import GetMultiline, Put
from pandablocks.ioc._tables import (
    TableFieldRecordContainer,
    TableModeEnum,
    TablePacking,
    _TableUpdater,
)
from pandablocks.ioc._types import (
    EpicsName,
    RecordValue,
    _InErrorException,
    _RecordInfo,
)
from pandablocks.responses import TableFieldDetails, TableFieldInfo

PANDA_FORMAT_TABLE_NAME = "SEQ1.TABLE"
EPICS_FORMAT_TABLE_NAME = "SEQ1:TABLE"


@pytest.fixture
def table_fields() -> Dict[str, TableFieldDetails]:
    """Table field definitions, taken from a SEQ.TABLE instance.
    Associated with table_data and table_field_info fixtures"""
    return {
        "REPEATS": TableFieldDetails(
            subtype="uint",
            bit_low=0,
            bit_high=15,
            description="Number of times the line will repeat ",
            labels=None,
        ),
        "TRIGGER": TableFieldDetails(
            subtype="enum",
            bit_low=16,
            bit_high=19,
            description="The trigger condition to start the phases ",
            labels=[
                "Immediate",
                "BITA=0",
                "BITA=1",
                "BITB=0",
                "BITB=1",
                "BITC=0",
                "BITC=1",
                "POSA>=POSITION",
                "POSA<=POSITION",
                "POSB>=POSITION",
                "POSB<=POSITION",
                "POSC>=POSITION",
                "POSC<=POSITION",
            ],
        ),
        "POSITION": TableFieldDetails(
            subtype="int",
            bit_low=32,
            bit_high=63,
            description="The position that can be used in trigger condition ",
            labels=None,
        ),
        "TIME1": TableFieldDetails(
            subtype="uint",
            bit_low=64,
            bit_high=95,
            description="The time the optional phase 1 should take ",
            labels=None,
        ),
        "OUTA1": TableFieldDetails(
            subtype="uint",
            bit_low=20,
            bit_high=20,
            description="Output A value during phase 1 ",
            labels=None,
        ),
        "OUTB1": TableFieldDetails(
            subtype="uint",
            bit_low=21,
            bit_high=21,
            description="Output B value during phase 1 ",
            labels=None,
        ),
        "OUTC1": TableFieldDetails(
            subtype="uint",
            bit_low=22,
            bit_high=22,
            description="Output C value during phase 1 ",
            labels=None,
        ),
        "OUTD1": TableFieldDetails(
            subtype="uint",
            bit_low=23,
            bit_high=23,
            description="Output D value during phase 1 ",
            labels=None,
        ),
        "OUTE1": TableFieldDetails(
            subtype="uint",
            bit_low=24,
            bit_high=24,
            description="Output E value during phase 1 ",
            labels=None,
        ),
        "OUTF1": TableFieldDetails(
            subtype="uint",
            bit_low=25,
            bit_high=25,
            description="Output F value during phase 1 ",
            labels=None,
        ),
        "TIME2": TableFieldDetails(
            subtype="uint",
            bit_low=96,
            bit_high=127,
            description="The time the mandatory phase 2 should take ",
            labels=None,
        ),
        "OUTA2": TableFieldDetails(
            subtype="uint",
            bit_low=26,
            bit_high=26,
            description="Output A value during phase 2 ",
            labels=None,
        ),
        "OUTB2": TableFieldDetails(
            subtype="uint",
            bit_low=27,
            bit_high=27,
            description="Output B value during phase 2 ",
            labels=None,
        ),
        "OUTC2": TableFieldDetails(
            subtype="uint",
            bit_low=28,
            bit_high=28,
            description="Output C value during phase 2 ",
            labels=None,
        ),
        "OUTD2": TableFieldDetails(
            subtype="uint",
            bit_low=29,
            bit_high=29,
            description="Output D value during phase 2 ",
            labels=None,
        ),
        "OUTE2": TableFieldDetails(
            subtype="uint",
            bit_low=30,
            bit_high=30,
            description="Output E value during phase 2 ",
            labels=None,
        ),
        "OUTF2": TableFieldDetails(
            subtype="uint",
            bit_low=31,
            bit_high=31,
            description="Output F value during phase 2 ",
            labels=None,
        ),
    }


@pytest.fixture
def table_field_info(table_fields) -> TableFieldInfo:
    """Table data associated with table_fields and table_data fixtures"""
    return TableFieldInfo(
        "table", None, "Test table description", 16384, table_fields, 4
    )


@pytest.fixture
def table_data() -> List[str]:
    """Table data associated with table_fields and table_field_info fixtures.
    See table_unpacked_data for the unpacked equivalent"""
    return [
        "2457862149",
        "4294967291",
        "100",
        "0",
        "269877248",
        "678",
        "0",
        "55",
        "4293968720",
        "0",
        "9",
        "9999",
    ]


@pytest.fixture
def table_data_dict(table_data: List[str]) -> Dict[EpicsName, RecordValue]:
    return {EpicsName(EPICS_FORMAT_TABLE_NAME): table_data}


@pytest.fixture
def table_unpacked_data(table_fields) -> Dict[EpicsName, ndarray]:
    """The unpacked equivalent of table_data"""
    array_values = [
        array([5, 0, 50000], dtype=uint16),
        array([0, 6, 0], dtype=uint8),
        array([-5, 678, 0], dtype=int32),
        array([100, 0, 9], dtype=uint32),
        array([0, 1, 1], dtype=uint8),
        array([0, 0, 1], dtype=uint8),
        array([0, 0, 1], dtype=uint8),
        array([1, 0, 1], dtype=uint8),
        array([0, 0, 1], dtype=uint8),
        array([1, 0, 1], dtype=uint8),
        array([0, 55, 9999], dtype=uint32),
        array([0, 0, 1], dtype=uint8),
        array([0, 0, 1], dtype=uint8),
        array([1, 1, 1], dtype=uint8),
        array([0, 0, 1], dtype=uint8),
        array([0, 0, 1], dtype=uint8),
        array([1, 0, 1], dtype=uint8),
    ]
    data = {}
    for field_name, data_array in zip(table_fields.keys(), array_values):
        data[field_name] = data_array

    return data


@pytest.fixture
def table_fields_records(
    table_fields: Dict[str, TableFieldDetails],
    table_unpacked_data: Dict[EpicsName, ndarray],
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
        record_info = _RecordInfo(mocked_record, lambda x: None)
        data[field_name] = TableFieldRecordContainer(field_info, record_info)
    return data


@pytest.fixture
def table_updater(
    table_field_info: TableFieldInfo,
    table_fields_records: Dict[str, TableFieldRecordContainer],
    table_data_dict: Dict[EpicsName, RecordValue],
) -> _TableUpdater:
    """Provides a _TableUpdater with configured records and mocked functionality"""
    client = AsyncioClient("123")
    client.send = AsyncMock()  # type: ignore
    # mypy doesn't play well with mocking so suppress error

    mocked_mode_record = MagicMock()
    # Default mode record to VIEW, as per default construction
    mocked_mode_record.get = MagicMock(return_value=TableModeEnum.VIEW.value)
    mocked_mode_record.set = MagicMock()
    mode_record_info = _RecordInfo(
        mocked_mode_record,
        lambda x: None,
        labels=[
            TableModeEnum.VIEW.name,
            TableModeEnum.EDIT.name,
            TableModeEnum.SUBMIT.name,
            TableModeEnum.DISCARD.name,
        ],
    )

    # The list of other records, i.e. SCALAR and INDEX, for the table
    other_records: Dict[EpicsName, _RecordInfo] = {
        EpicsName("SEQ1:TABLE:POSITION:SCALAR"): MagicMock(),
        EpicsName("SEQ1:TABLE:INDEX"): MagicMock(),
    }

    updater = _TableUpdater(
        client,
        EpicsName(EPICS_FORMAT_TABLE_NAME),
        table_field_info,
        table_fields_records,
        other_records,
        table_data_dict,
    )

    updater.set_mode_record_info(mode_record_info)

    return updater


def test_table_packing_unpack(
    table_field_info: TableFieldInfo,
    table_fields_records: Dict[str, TableFieldRecordContainer],
    table_data: List[str],
    table_unpacked_data,
):
    """Test table unpacking works as expected"""
    assert table_field_info.row_words
    unpacked = TablePacking.unpack(
        table_field_info.row_words, table_fields_records, table_data
    )

    for actual, expected in zip(unpacked, table_unpacked_data.values()):
        assert numpy.array_equal(actual, expected)


def test_table_packing_pack(
    table_field_info: TableFieldInfo,
    table_fields_records: Dict[str, TableFieldRecordContainer],
    table_data: List[str],
):
    """Test table unpacking works as expected"""
    assert table_field_info.row_words
    unpacked = TablePacking.pack(table_field_info.row_words, table_fields_records)

    for actual, expected in zip(unpacked, table_data):
        assert actual == expected


def test_table_packing_pack_length_mismatched(
    table_field_info: TableFieldInfo,
    table_fields_records: Dict[str, TableFieldRecordContainer],
):
    """Test that mismatching lengths on waveform inputs causes an exception"""
    assert table_field_info.row_words

    # Adjust one of the record lengths so it mismatches
    record_info = table_fields_records[EpicsName("OUTC1")].record_info
    assert record_info
    record_info.record.get = MagicMock(return_value=array([1, 2, 3, 4, 5, 6, 7, 8]))

    with pytest.raises(AssertionError):
        TablePacking.pack(table_field_info.row_words, table_fields_records)


def test_table_packing_roundtrip(
    table_field_info: TableFieldInfo,
    table_fields: Dict[str, TableFieldDetails],
    table_fields_records: Dict[str, TableFieldRecordContainer],
    table_data: List[str],
):
    """Test that calling unpack -> pack yields the same data"""
    assert table_field_info.row_words
    unpacked = TablePacking.unpack(
        table_field_info.row_words, table_fields_records, table_data
    )

    # Put these values into Mocks for the Records
    data: Dict[str, TableFieldRecordContainer] = {}
    for (field_name, field_info), data_array in zip(table_fields.items(), unpacked):
        mocked_record = MagicMock()
        mocked_record.get = MagicMock(return_value=data_array)
        record_info = _RecordInfo(mocked_record, lambda x: None)
        data[field_name] = TableFieldRecordContainer(field_info, record_info)

    packed = TablePacking.pack(table_field_info.row_words, data)

    assert packed == table_data


def test_table_updater_fields_sorted(table_updater: _TableUpdater):
    """Test that the field sorting done in post_init has occurred"""

    # Bits start at 0
    curr_bit = -1
    for field in table_updater.table_fields_records.values():
        field_details = field.field
        assert curr_bit < field_details.bit_low, "Fields are not in bit order"
        assert (
            field_details.bit_low <= field_details.bit_high  # fields may be 1 bit wide
        ), "Field had incorrect bit_low and bit_high order"
        assert (
            curr_bit < field_details.bit_high
        ), "Field had bit_high lower than bit_low"
        curr_bit = field_details.bit_high


def test_table_updater_validate_mode_view(table_updater: _TableUpdater):
    """Test the validate method when mode is View"""

    # View is default in table_updater
    record = MagicMock()
    record.name = MagicMock(return_value="NewRecord")
    assert table_updater.validate_waveform(record, "value is irrelevant") is False


def test_table_updater_validate_mode_edit(table_updater: _TableUpdater):
    """Test the validate method when mode is Edit"""

    table_updater._mode_record_info.record.get = MagicMock(
        return_value=TableModeEnum.EDIT.value
    )

    record = MagicMock()
    record.name = MagicMock(return_value="NewRecord")
    assert table_updater.validate_waveform(record, "value is irrelevant") is True


def test_table_updater_validate_mode_submit(table_updater: _TableUpdater):
    """Test the validate method when mode is Submit"""

    table_updater._mode_record_info.record.get = MagicMock(
        return_value=TableModeEnum.SUBMIT.value
    )

    record = MagicMock()
    record.name = MagicMock(return_value="NewRecord")
    assert table_updater.validate_waveform(record, "value is irrelevant") is False


def test_table_updater_validate_mode_discard(table_updater: _TableUpdater):
    """Test the validate method when mode is Discard"""

    table_updater._mode_record_info.record.get = MagicMock(
        return_value=TableModeEnum.DISCARD.value
    )

    record = MagicMock()
    record.name = MagicMock(return_value="NewRecord")
    assert table_updater.validate_waveform(record, "value is irrelevant") is False


def test_table_updater_validate_mode_unknown(table_updater: _TableUpdater):
    """Test the validate method when mode is unknown"""

    table_updater._mode_record_info.record.get = MagicMock(return_value="UnknownValue")
    table_updater._mode_record_info.record.set_alarm = MagicMock()

    record = MagicMock()
    record.name = MagicMock(return_value="NewRecord")

    assert table_updater.validate_waveform(record, "value is irrelevant") is False
    table_updater._mode_record_info.record.set_alarm.assert_called_once_with(
        alarm.INVALID_ALARM, alarm.UDF_ALARM
    )


@pytest.mark.asyncio
async def test_table_updater_update_mode_view(table_updater: _TableUpdater):
    """Test that update_mode with new value of VIEW takes no action"""
    await table_updater.update_mode(TableModeEnum.VIEW.value)

    assert (
        not table_updater.client.send.called  # type: ignore
    ), "client send method was unexpectedly called"
    assert (
        not table_updater._mode_record_info.record.set.called
    ), "record set method was unexpectedly called"


@pytest.mark.asyncio
async def test_table_updater_update_mode_submit(
    table_updater: _TableUpdater, table_data: List[str]
):
    """Test that update_mode with new value of SUBMIT sends data to PandA"""
    await table_updater.update_mode(TableModeEnum.SUBMIT.value)

    assert isinstance(table_updater.client.send, AsyncMock)
    table_updater.client.send.assert_called_once_with(
        Put(PANDA_FORMAT_TABLE_NAME, table_data)
    )

    table_updater._mode_record_info.record.set.assert_called_once_with(
        TableModeEnum.VIEW.value, process=False
    )


@pytest.mark.asyncio
async def test_table_updater_update_mode_submit_exception(
    table_updater: _TableUpdater,
    table_data: List[str],
    table_unpacked_data: Dict[EpicsName, ndarray],
):
    """Test that update_mode with new value of SUBMIT handles an exception from Put
    correctly"""

    assert isinstance(table_updater.client.send, AsyncMock)
    table_updater.client.send.side_effect = Exception("Mocked exception")

    await table_updater.update_mode(TableModeEnum.SUBMIT.value)

    table_updater.client.send.assert_called_once_with(
        Put(PANDA_FORMAT_TABLE_NAME, table_data)
    )

    # Confirm each record received the expected data
    for field_name, data in table_unpacked_data.items():
        # Note table_unpacked_data is deliberately in a different order to the sorted
        # data, hence use this lookup mechanism instead
        record_info = table_updater.table_fields_records[field_name].record_info
        assert record_info
        # numpy arrays don't play nice with mock's equality comparisons, do it ourself
        called_args = record_info.record.set.call_args

        numpy.testing.assert_array_equal(data, called_args[0][0])

    table_updater._mode_record_info.record.set.assert_called_once_with(
        TableModeEnum.VIEW.value, process=False
    )


@pytest.mark.asyncio
async def test_table_updater_update_mode_submit_exception_data_error(
    table_updater: _TableUpdater, table_data: List[str]
):
    """Test that update_mode with an exception from Put and an InErrorException behaves
    as expected"""
    assert isinstance(table_updater.client.send, AsyncMock)
    table_updater.client.send.side_effect = Exception("Mocked exception")

    table_updater.all_values_dict[
        EpicsName(EPICS_FORMAT_TABLE_NAME)
    ] = _InErrorException("Mocked in error exception")

    await table_updater.update_mode(TableModeEnum.SUBMIT.value)

    for field_record in table_updater.table_fields_records.values():
        assert field_record.record_info
        record = field_record.record_info.record
        record.set.assert_not_called()

    table_updater.client.send.assert_called_once_with(
        Put(PANDA_FORMAT_TABLE_NAME, table_data)
    )


@pytest.mark.asyncio
async def test_table_updater_update_mode_discard(
    table_updater: _TableUpdater,
    table_data: List[str],
    table_unpacked_data: Dict[EpicsName, ndarray],
):
    """Test that update_mode with new value of DISCARD resets record data"""
    assert isinstance(table_updater.client.send, AsyncMock)
    table_updater.client.send.return_value = table_data

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

        numpy.testing.assert_array_equal(data, called_args[0][0])

    table_updater._mode_record_info.record.set.assert_called_once_with(
        TableModeEnum.VIEW.value, process=False
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "enum_val", [TableModeEnum.EDIT.value, TableModeEnum.VIEW.value]
)
async def test_table_updater_update_mode_other(
    table_updater: _TableUpdater,
    table_unpacked_data: Dict[EpicsName, ndarray],
    enum_val: int,
):
    """Test that update_mode with non-SUBMIT or DISCARD values takes no action"""

    await table_updater.update_mode(enum_val)

    assert isinstance(table_updater.client.send, AsyncMock)
    table_updater.client.send.assert_not_called()

    # Confirm each record was not called
    for field_name, data in table_unpacked_data.items():
        record_info = table_updater.table_fields_records[field_name].record_info
        assert record_info

        record_info.record.assert_not_called()

    table_updater._mode_record_info.record.set.assert_not_called()


def test_table_updater_update_table(
    table_updater: _TableUpdater,
    table_data: List[str],
    table_unpacked_data: Dict[EpicsName, ndarray],
):
    """Test that update_table updates records with the new values"""

    # update_scalar is too complex to test as well, so mock it out
    table_updater._update_scalar = MagicMock()  # type: ignore

    table_updater.update_table(table_data)

    table_updater._mode_record_info.record.get.assert_called_once()

    # Confirm each record received the expected data
    for field_name, data in table_unpacked_data.items():
        # Note table_unpacked_data is deliberately in a different order to the sorted
        # data, hence use this lookup mechanism instead
        record_info = table_updater.table_fields_records[field_name].record_info
        assert record_info
        # numpy arrays don't play nice with mock's equality comparisons, do it ourself
        called_args = record_info.record.set.call_args

        numpy.testing.assert_array_equal(data, called_args[0][0])

    table_updater._update_scalar.assert_called()


def test_table_updater_update_table_not_view(
    table_updater: _TableUpdater,
    table_data: List[str],
    table_unpacked_data: Dict[EpicsName, ndarray],
):
    """Test that update_table does nothing when mode is not VIEW"""

    # update_scalar is too complex to test as well, so mock it out
    table_updater._update_scalar = MagicMock()  # type: ignore

    table_updater._mode_record_info.record.get.return_value = TableModeEnum.EDIT

    table_updater.update_table(table_data)

    table_updater._mode_record_info.record.get.assert_called_once()

    # Confirm the records were not called
    for field_name, data in table_unpacked_data.items():
        # Note table_unpacked_data is deliberately in a different order to the sorted
        # data, hence use this lookup mechanism instead
        record_info = table_updater.table_fields_records[field_name].record_info
        assert record_info
        record_info.record.set.assert_not_called()


@pytest.mark.asyncio
async def test_table_updater_update_index(
    table_updater: _TableUpdater,
    table_fields: Dict[str, TableFieldDetails],
):
    """Test that update_index passes the full list of records to _update_scalar"""

    # Just need to prove it was called, not that it ran
    table_updater._update_scalar = MagicMock()  # type: ignore

    await table_updater.update_index(None)

    calls = []
    for field in table_fields.keys():
        calls.append(call(EPICS_FORMAT_TABLE_NAME + ":" + field))

    table_updater._update_scalar.assert_has_calls(calls, any_order=True)


def test_table_updater_update_scalar(
    table_updater: _TableUpdater,
):
    """Test that update_scalar correctly updates the scalar record for a waveform"""
    scalar_record_name = EpicsName("SEQ1:TABLE:POSITION:SCALAR")
    scalar_record = table_updater.table_records[scalar_record_name].record

    index_record_name = EpicsName("SEQ1:TABLE:INDEX")
    index_record = table_updater.table_records[index_record_name].record
    index_record.get.return_value = 1

    table_updater._update_scalar("ABC:SEQ1:TABLE:POSITION")

    scalar_record.set.assert_called_once_with(
        678, severity=alarm.NO_ALARM, alarm=alarm.UDF_ALARM
    )


def test_table_updater_update_scalar_index_out_of_bounds(
    table_updater: _TableUpdater,
):
    """Test that update_scalar handles an invalid index"""
    scalar_record_name = EpicsName("SEQ1:TABLE:POSITION:SCALAR")
    scalar_record = table_updater.table_records[scalar_record_name].record

    index_record_name = EpicsName("SEQ1:TABLE:INDEX")
    index_record = table_updater.table_records[index_record_name].record
    index_record.get.return_value = 99

    table_updater._update_scalar("ABC:SEQ1:TABLE:POSITION")

    scalar_record.set.assert_called_once_with(
        0, severity=alarm.INVALID_ALARM, alarm=alarm.UDF_ALARM
    )
