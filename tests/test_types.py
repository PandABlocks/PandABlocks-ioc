import pytest

from pandablocks_ioc._types import (
    EpicsName,
    PandAName,
    epics_to_panda_name,
    epics_to_pvi_name,
    panda_to_epics_name,
    trim_description,
    trim_string_value,
)


def test_panda_to_epics_name_conversion() -> None:
    assert panda_to_epics_name(PandAName("ABC.123.456")) == EpicsName("ABC:123:456")


def test_epics_to_panda_name_conversion() -> None:
    assert epics_to_panda_name(EpicsName("ABC:123:456")) == PandAName("ABC.123.456")


def test_panda_to_epics_and_back_name_conversion() -> None:
    """Test panda->EPICS->panda round trip name conversion works"""
    assert epics_to_panda_name(
        panda_to_epics_name(PandAName("ABC.123.456"))
    ) == PandAName("ABC.123.456")


@pytest.mark.parametrize(
    "arg_result",
    [
        ("WOW:WHAT:A_THINGY", "AThingy"),
        ("WOW:WHAT:A-THINGY", "AThingy"),
        ("WOW:WHAT:aTHINGY", "Athingy"),
        ("WOW:WHAT:A_THINGY123", "AThingy123"),
        ("WOW:WHAT:A-THINGY_123", "AThingy123"),
    ],
)
def test_epics_to_pvi_name(arg_result):
    arg, result = arg_result
    assert epics_to_pvi_name(arg) == result


def test_string_value():
    """Test trim_string_values for a few cases"""
    assert trim_string_value("ABC", "SomeRecordName") == "ABC"
    assert trim_string_value("", "SomeRecordName") == ""
    long_value = "a very long string too long to fit in fact"
    assert trim_string_value(long_value, "SomeRecordName") == long_value[0:39]


def test_trim_description():
    """Test trim_description for a few cases"""
    assert trim_description("ABC", "SomeRecordName") == "ABC"
    long_desc = "a very long string too long to fit in fact"
    assert trim_description(long_desc, "SomeRecordName") == long_desc[0:39]
    assert trim_description(None, "SomeRecordName") is None
