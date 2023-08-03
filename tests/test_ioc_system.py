import asyncio
import filecmp
import os
import typing
from pathlib import Path
from typing import List

import numpy
import pytest
from aioca import caget, camonitor, caput
from fixtures.mocked_panda import BOBFILE_DIR, TEST_PREFIX, TIMEOUT
from numpy import ndarray
from pandablocks.asyncio import AsyncioClient
from pandablocks_ioc._types import EpicsName
from pandablocks_ioc.ioc import (
    _ensure_block_number_present,
)

# Test file for all tests that require a full setup system, with an IOC running in one
# process, a MockedServer in another, and the test in the main thread accessing data
# using Channel Access


@pytest.mark.asyncio
async def test_create_softioc_system(
    mocked_panda_standard_responses,
    table_unpacked_data: typing.OrderedDict[EpicsName, ndarray],
):
    """Top-level system test of the entire program, using some pre-canned data. Tests
    that the input data is turned into a collection of records with the appropriate
    values."""
    # Check table fields
    for field_name, expected_array in table_unpacked_data.items():
        actual_array = await caget(TEST_PREFIX + ":SEQ1:TABLE:" + field_name)
        assert numpy.array_equal(actual_array, expected_array)

    assert await caget(TEST_PREFIX + ":PCAP1:TRIG_EDGE") == 1  # == Falling
    assert await caget(TEST_PREFIX + ":PCAP1:GATE") == "CLOCK1.OUT"
    assert await caget(TEST_PREFIX + ":PCAP1:GATE:DELAY") == 1

    pcap1_label = await caget(TEST_PREFIX + ":PCAP1:LABEL")
    assert numpy.array_equal(
        pcap1_label,
        numpy.array(list("PcapMetadataLabel".encode() + b"\0"), dtype=numpy.uint8),
    )


@pytest.mark.asyncio
async def test_create_softioc_update(
    mocked_panda_standard_responses,
):
    """Test that the update mechanism correctly changes record values when PandA
    reports values have changed"""

    # Add more GetChanges data. Include some trailing empty changesets to allow test
    try:
        # Set up a monitor to wait for the expected change
        capturing_queue: asyncio.Queue = asyncio.Queue()
        monitor = camonitor(TEST_PREFIX + ":PCAP1:TRIG_EDGE", capturing_queue.put)

        curr_val = await asyncio.wait_for(capturing_queue.get(), TIMEOUT)
        # First response is the current value
        assert curr_val == 1

        # Wait for the new value to appear
        curr_val = await asyncio.wait_for(capturing_queue.get(), TIMEOUT)
        assert curr_val == 2

    finally:
        monitor.close()


# TODO: Enable this test once PythonSoftIOC issue #53 is resolved
# @pytest.mark.asyncio
# async def test_create_softioc_update_in_error(
#     mocked_server_system,
#     subprocess_ioc,
# ):
#     """Test that the update mechanism correctly marks records as in error when PandA
#     reports the associated field is in error"""

#     # Add more GetChanges data. Include some trailing empty changesets to allow test
#     # code to run.
#     mocked_server_system.send += [
#         "!PCAP1.TRIG_EDGE (error)\n.",
#         ".",
#         ".",
#         ".",
#         ".",
#         ".",
#         ".",
#     ]

#     try:
#         # Set up a monitor to wait for the expected change
#         capturing_queue: asyncio.Queue = asyncio.Queue()
#         monitor = camonitor(TEST_PREFIX + ":PCAP1:TRIG_EDGE", capturing_queue.put)

#         curr_val = await asyncio.wait_for(capturing_queue.get(), 2)
#         # First response is the current value
#         assert curr_val == 1

# # Wait for the new value to appear
# Cannot do this due to PythonSoftIOC issue #53.
# err_val: AugmentedValue = await asyncio.wait_for(capturing_queue.get(), 100)
# assert err_val.severity == alarm.INVALID_ALARM
# assert err_val.status == alarm.UDF_ALARM

#     finally:
#         monitor.close()
#         purge_channel_caches()


def test_ensure_block_number_present():
    assert _ensure_block_number_present("ABC.DEF.GHI") == "ABC1.DEF.GHI"
    assert _ensure_block_number_present("JKL1.MNOP") == "JKL1.MNOP"


@pytest.mark.asyncio
async def test_create_softioc_time_epics_changes(
    mocked_panda_standard_responses,
):
    """Test that the UNITS and MIN values of a TIME field correctly sent to the PandA
    when an EPICS record is updated"""
    try:
        # Set up monitors for expected changes when the UNITS are changed,
        # and check the initial values are correct
        egu_queue: asyncio.Queue = asyncio.Queue()
        m1 = camonitor(
            TEST_PREFIX + ":PULSE1:DELAY.EGU",
            egu_queue.put,
        )
        assert await asyncio.wait_for(egu_queue.get(), TIMEOUT) == "ms"

        units_queue: asyncio.Queue = asyncio.Queue()
        m2 = camonitor(
            TEST_PREFIX + ":PULSE1:DELAY:UNITS", units_queue.put, datatype=str
        )
        assert await asyncio.wait_for(units_queue.get(), TIMEOUT) == "ms"

        drvl_queue: asyncio.Queue = asyncio.Queue()
        m3 = camonitor(
            TEST_PREFIX + ":PULSE1:DELAY.DRVL",
            drvl_queue.put,
        )
        assert await asyncio.wait_for(drvl_queue.get(), TIMEOUT) == 8e-06

        assert await asyncio.wait_for(egu_queue.get(), TIMEOUT) == "s"
        assert await asyncio.wait_for(units_queue.get(), TIMEOUT) == "s"

        # Change the UNITS to "min"
        assert await caput(
            TEST_PREFIX + ":PULSE1:DELAY:UNITS", 0, wait=True, timeout=TIMEOUT
        )

        assert await asyncio.wait_for(egu_queue.get(), TIMEOUT) == "min"
        assert await asyncio.wait_for(units_queue.get(), TIMEOUT) == "min"
        assert await asyncio.wait_for(drvl_queue.get(), TIMEOUT) == 1.333333333e-10

    finally:
        m1.close()
        m2.close()
        m3.close()


@pytest.mark.asyncio
async def test_softioc_records_block(mocked_panda_standard_responses):
    """Test that the records created are blocking, and wait until they finish their
    on_update processing.

    Note that a lot of other tests implicitly test this feature too - any test that
    uses caput with wait=True is effectively testing this."""

    try:
        # Set the special response for the server
        arm_queue: asyncio.Queue = asyncio.Queue()
        m1 = camonitor(TEST_PREFIX + ":PCAP:ARM", arm_queue.put, datatype=str)
        assert await asyncio.wait_for(arm_queue.get(), TIMEOUT) == "0"

        await caput(TEST_PREFIX + ":PCAP:ARM", 1, wait=True, timeout=TIMEOUT)

        assert await asyncio.wait_for(arm_queue.get(), TIMEOUT) == "1"
    finally:
        m1.close()


@pytest.mark.asyncio
async def test_bobfiles_created(mocked_panda_standard_responses):
    # TODO: SAVE NEW BOBFILES NOW THEY'VE BEEN CREATED
    bobfile_temp_dir, *_ = mocked_panda_standard_responses
    assert bobfile_temp_dir.exists() and BOBFILE_DIR.exists()
    old_files = os.listdir(BOBFILE_DIR)
    for file in old_files:
        assert filecmp.cmp(
            f"{bobfile_temp_dir}/{file}", f"{BOBFILE_DIR}/{file}"
        ), f"File {bobfile_temp_dir/file} does not match {BOBFILE_DIR/file}"

    # And check that the same number of files are created
    new_files = os.listdir(bobfile_temp_dir)
    assert len(old_files) == len(new_files)
