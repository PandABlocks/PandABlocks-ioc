import asyncio
from pathlib import Path
from typing import List, OrderedDict

import numpy
import pytest
from aioca import DBR_CHAR_STR, CANothing, caget, camonitor, caput
from numpy import ndarray
from pandablocks.commands import Arm, Disarm, Put
from pandablocks.responses import (
    BitMuxFieldInfo,
    BlockInfo,
    EnumFieldInfo,
    TableFieldInfo,
)
from pvi.device import SignalX

from fixtures.mocked_panda import (
    BOBFILE_DIR,
    TEST_PREFIX,
    TIMEOUT,
    MockedAsyncioClient,
    ResponseHandler,
    command_to_key,
    multiprocessing_queue_to_list,
)
from pandablocks_ioc._pvi import Pvi, PviGroup
from pandablocks_ioc._types import EpicsName
from pandablocks_ioc.ioc import _BlockAndFieldInfo, introspect_panda

# Test file for all tests that require a full setup system, with an IOC running in one
# process, a MockedServer in another, and the test in the main thread accessing data
# using Channel Access


async def test_introspect_panda(
    standard_responses,
    table_field_info: TableFieldInfo,
    table_data_1: List[str],
):
    """High-level test that introspect_panda returns expected data structures"""
    client = MockedAsyncioClient(ResponseHandler(standard_responses))
    (data, all_values_dict) = await introspect_panda(client)
    assert data["PCAP"] == _BlockAndFieldInfo(
        block_info=BlockInfo(number=1, description="PCAP Desc"),
        fields={
            "TRIG_EDGE": EnumFieldInfo(
                type="param",
                subtype="enum",
                description="Trig Edge Desc",
                labels=["Rising", "Falling", "Either"],
            ),
            "GATE": BitMuxFieldInfo(
                type="bit_mux",
                subtype=None,
                description="Gate Desc",
                max_delay=100,
                labels=["TTLIN1.VAL", "INENC1.A", "CLOCK1.OUT"],
            ),
        },
        values={
            EpicsName("PCAP:TRIG_EDGE"): "Falling",
            EpicsName("PCAP:GATE"): "CLOCK1.OUT",
            EpicsName("PCAP:GATE:DELAY"): "1",
            EpicsName("PCAP:LABEL"): "PcapMetadataLabel",
            EpicsName("PCAP:ARM"): "0",
        },
    )

    assert data["SEQ"] == _BlockAndFieldInfo(
        block_info=BlockInfo(number=1, description="SEQ Desc"),
        fields={
            "TABLE": table_field_info,
        },
        values={EpicsName("SEQ:TABLE"): table_data_1},
    )

    assert all_values_dict == {
        "PCAP:TRIG_EDGE": "Falling",
        "PCAP:GATE": "CLOCK1.OUT",
        "PCAP:GATE:DELAY": "1",
        "PCAP:LABEL": "PcapMetadataLabel",
        "PULSE:DELAY": "100",
        "PCAP:ARM": "0",
        "PULSE:DELAY:MIN": "8e-06",
        "PULSE:DELAY:UNITS": "ms",
        "SEQ:TABLE": table_data_1,
    }


async def test_create_softioc_system(
    mocked_panda_standard_responses_no_panda_update,
    table_unpacked_data: OrderedDict[EpicsName, ndarray],
):
    """Top-level system test of the entire program, using some pre-canned data. Tests
    that the input data is turned into a collection of records with the appropriate
    values."""
    # Check table fields
    (
        tmp_path,
        child_conn,
        response_handler,
        command_queue,
        test_prefix,
    ) = mocked_panda_standard_responses_no_panda_update

    for field_name, expected_array in table_unpacked_data.items():
        actual_array = await caget(test_prefix + ":SEQ:TABLE:" + field_name)
        assert numpy.array_equal(actual_array, expected_array)

    assert await caget(test_prefix + ":PCAP:TRIG_EDGE") == 1  # == Falling
    assert await caget(test_prefix + ":PCAP:GATE") == "CLOCK1.OUT"
    assert await caget(test_prefix + ":PCAP:GATE:DELAY") == 1

    pcap1_label = await caget(test_prefix + ":PCAP:LABEL")
    assert numpy.array_equal(
        pcap1_label,
        numpy.array(list(b"PcapMetadataLabel" + b"\0"), dtype=numpy.uint8),
    )


async def test_create_softioc_update(
    mocked_panda_standard_responses,
):
    """Test that the update mechanism correctly changes record values when PandA
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
        monitor = camonitor(test_prefix + ":PCAP:TRIG_EDGE", capturing_queue.put)

        curr_val = await asyncio.wait_for(capturing_queue.get(), TIMEOUT)
        # First response is the current value
        assert curr_val == 1

        # Wait for the new value to appear
        curr_val = await asyncio.wait_for(capturing_queue.get(), TIMEOUT)
        assert curr_val == 2

    finally:
        monitor.close()


async def test_including_number_in_block_names_throws_error(
    faulty_multiple_pcap_responses,
):
    response_handler = ResponseHandler(faulty_multiple_pcap_responses)
    mocked_client = MockedAsyncioClient(response_handler)

    with pytest.raises(ValueError):
        await introspect_panda(mocked_client)


# TODO: Enable this test once PythonSoftIOC issue #53 is resolved
#
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


async def test_create_softioc_time_panda_changes(mocked_panda_standard_responses):
    """Test that the UNITS and MIN values of a TIME field correctly reflect into EPICS
    records when the value changes on the PandA"""
    (
        tmp_path,
        child_conn,
        response_handler,
        command_queue,
        test_prefix,
    ) = mocked_panda_standard_responses
    try:
        # Set up monitors for expected changes when the UNITS are changed,
        # and check the initial values are correct
        egu_queue = asyncio.Queue()
        m1 = camonitor(
            test_prefix + ":PULSE:DELAY.EGU",
            egu_queue.put,
        )
        assert await asyncio.wait_for(egu_queue.get(), TIMEOUT) == "ms"

        units_queue = asyncio.Queue()
        m2 = camonitor(
            test_prefix + ":PULSE:DELAY:UNITS", units_queue.put, datatype=str
        )
        assert await asyncio.wait_for(units_queue.get(), TIMEOUT) == "ms"

        drvl_queue = asyncio.Queue()
        m3 = camonitor(
            test_prefix + ":PULSE:DELAY.DRVL",
            drvl_queue.put,
        )
        # The units value changes from ms to s in the test Client, which causes
        # the DRVL value to change from 8e-06 to 8e-09, consistent to ms to s.

        assert await asyncio.wait_for(drvl_queue.get(), TIMEOUT) == 8e-06
        assert await asyncio.wait_for(egu_queue.get(), TIMEOUT) == "s"
        assert await asyncio.wait_for(units_queue.get(), TIMEOUT) == "s"
        assert await asyncio.wait_for(drvl_queue.get(), TIMEOUT) == 8e-09
    finally:
        m1.close()
        m2.close()
        m3.close()


async def test_create_softioc_time_epics_changes(
    mocked_panda_standard_responses,
):
    """Test that the UNITS and MIN values of a TIME field correctly sent to the PandA
    when an EPICS record is updated"""
    (
        tmp_path,
        child_conn,
        response_handler,
        command_queue,
        test_prefix,
    ) = mocked_panda_standard_responses
    try:
        # Set up monitors for expected changes when the UNITS are changed,
        # and check the initial values are correct
        egu_queue = asyncio.Queue()
        m1 = camonitor(
            test_prefix + ":PULSE:DELAY.EGU",
            egu_queue.put,
        )
        assert await asyncio.wait_for(egu_queue.get(), TIMEOUT) == "ms"

        units_queue = asyncio.Queue()
        m2 = camonitor(
            test_prefix + ":PULSE:DELAY:UNITS", units_queue.put, datatype=str
        )
        assert await asyncio.wait_for(units_queue.get(), TIMEOUT) == "ms"

        drvl_queue = asyncio.Queue()
        m3 = camonitor(
            test_prefix + ":PULSE:DELAY.DRVL",
            drvl_queue.put,
        )
        assert await asyncio.wait_for(drvl_queue.get(), TIMEOUT) == 8e-06

        assert await asyncio.wait_for(egu_queue.get(), TIMEOUT) == "s"
        assert await asyncio.wait_for(units_queue.get(), TIMEOUT) == "s"
        assert await asyncio.wait_for(drvl_queue.get(), TIMEOUT) == 8e-09

        # Change the UNITS to "min"
        assert await caput(
            test_prefix + ":PULSE:DELAY:UNITS", "min", wait=True, timeout=TIMEOUT
        )

        assert await asyncio.wait_for(egu_queue.get(), TIMEOUT) == "min"
        assert await asyncio.wait_for(units_queue.get(), TIMEOUT) == "min"
        assert await asyncio.wait_for(drvl_queue.get(), TIMEOUT) == 1.333333333e-10

    finally:
        m1.close()
        m2.close()
        m3.close()


async def test_softioc_records_block(mocked_panda_standard_responses):
    """Test that the records created are blocking, and wait until they finish their
    on_update processing.

    Note that a lot of other tests implicitly test this feature too - any test that
    uses caput with wait=True is effectively testing this."""
    (
        tmp_path,
        child_conn,
        response_handler,
        command_queue,
        test_prefix,
    ) = mocked_panda_standard_responses
    try:
        arm_queue = asyncio.Queue()
        m1 = camonitor(test_prefix + ":PCAP:ARM", arm_queue.put, datatype=str)
        assert await asyncio.wait_for(arm_queue.get(), TIMEOUT) == "Disarm"

        await caput(test_prefix + ":PCAP:ARM", 1, wait=True, timeout=TIMEOUT)

        assert await asyncio.wait_for(arm_queue.get(), TIMEOUT) == "Arm"
    finally:
        m1.close()


async def test_bobfiles_created(mocked_panda_standard_responses):
    (
        bobfile_temp_dir,
        child_conn,
        response_handler,
        command_queue,
        test_prefix,
    ) = mocked_panda_standard_responses

    assert bobfile_temp_dir.exists() and BOBFILE_DIR.exists()

    MISMATCHED_OUTPUT_MESSAGE = (
        "Generated test bobfiles do not match `tests/test-bobfiles`. "
        "If changes have been made that would result in different bobfiles "
        "generated then regenerate the `test-bobfiles` with "
        "`tests/regenerate_test_bobfiles.sh`."
    )

    # Wait for the files to be created in the subprocess.
    await asyncio.sleep(1)

    old_files = [
        file_path
        for file_path in Path.iterdir(BOBFILE_DIR)
        if file_path.suffix == ".bob"
    ]
    for file_path in old_files:
        assert (
            Path(bobfile_temp_dir / file_path.name)
            .read_text()
            .replace(test_prefix, TEST_PREFIX)
            == file_path.read_text()
        ), MISMATCHED_OUTPUT_MESSAGE

    # And check that the same number of files are created
    new_files = list(Path.iterdir(bobfile_temp_dir))
    assert len(old_files) == len(new_files), MISMATCHED_OUTPUT_MESSAGE


async def test_create_bobfiles_fails_if_files_present(tmp_path, new_random_test_prefix):
    Path(tmp_path / "PCAP.bob").touch()

    with pytest.raises(FileExistsError):
        Pvi.configure_pvi(tmp_path, False)
        Pvi.create_pvi_records(new_random_test_prefix)


async def test_create_bobfiles_deletes_existing_files_with_clear_bobfiles(
    tmp_path,
    new_random_test_prefix,
    clear_records,
):
    generated_bobfile = Path(tmp_path / "index.bob")
    non_generated_bobfile = Path(tmp_path / "Blahblah.bob")
    non_bobfile = Path(tmp_path / "Blahblah.txt")

    generated_bobfile.touch()
    assert generated_bobfile.read_text() == ""
    non_generated_bobfile.touch()
    non_bobfile.touch()

    Pvi.configure_pvi(tmp_path, True)
    pv = new_random_test_prefix + ":PCAP:TRIG_EDGE"
    Pvi.add_pvi_info(
        pv,
        PviGroup.PARAMETERS,
        SignalX(name="TrigEdge", pv=pv, value="Falling"),
    )
    Pvi.create_pvi_records(new_random_test_prefix)

    assert not non_generated_bobfile.is_file()
    assert non_bobfile.is_file()
    assert generated_bobfile.is_file()
    assert generated_bobfile.read_text() != ""


async def test_create_softioc_record_update_send_to_panda(
    mocked_panda_standard_responses,
):
    """Test that updating a record causes the new value to be sent to PandA"""
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

        # Verify the pv has been put to
        await caput(
            test_prefix + ":PCAP:TRIG_EDGE", "Falling", wait=True, timeout=TIMEOUT
        )
        assert await asyncio.wait_for(trig_queue.get(), TIMEOUT) == "Falling"
    finally:
        m1.close()

    # Give the queue time to be put to
    await asyncio.sleep(0.1)

    # Check the panda recieved the translated command
    commands_recieved_by_panda = multiprocessing_queue_to_list(command_queue)
    assert (
        command_to_key(Put(field="PCAP.TRIG_EDGE", value="Falling"))
        in commands_recieved_by_panda
    )


async def test_create_softioc_arm_disarm(
    mocked_panda_standard_responses,
):
    """Test that the Arm and Disarm commands are correctly sent to PandA"""

    (
        tmp_path,
        child_conn,
        response_handler,
        command_queue,
        test_prefix,
    ) = mocked_panda_standard_responses

    try:
        arm_queue = asyncio.Queue()
        m1 = camonitor(test_prefix + ":PCAP:ARM", arm_queue.put, datatype=str)
        assert await asyncio.wait_for(arm_queue.get(), TIMEOUT) == "Disarm"

        # Put PVs and check the ioc sets the values
        await caput(test_prefix + ":PCAP:ARM", "1", wait=True, timeout=TIMEOUT)
        assert await asyncio.wait_for(arm_queue.get(), TIMEOUT) == "Arm"
        await caput(test_prefix + ":PCAP:ARM", "0", wait=True, timeout=TIMEOUT)
        assert await asyncio.wait_for(arm_queue.get(), TIMEOUT) == "Disarm"

        # Test you can also use "Arm" and "Disarm" instead of "1" and "0"
        await caput(test_prefix + ":PCAP:ARM", "Arm", wait=True, timeout=TIMEOUT)
        assert await asyncio.wait_for(arm_queue.get(), TIMEOUT) == "Arm"
        await caput(test_prefix + ":PCAP:ARM", "Disarm", wait=True, timeout=TIMEOUT)
        assert await asyncio.wait_for(arm_queue.get(), TIMEOUT) == "Disarm"

    finally:
        m1.close()

    # Give the queue time to be put to
    await asyncio.sleep(0.1)

    # Check the panda recieved the translated commands
    commands_recieved_by_panda = multiprocessing_queue_to_list(command_queue)
    assert command_to_key(Arm()) in commands_recieved_by_panda
    assert command_to_key(Disarm()) in commands_recieved_by_panda


async def test_multiple_seq_pvs_are_numbered(
    mocked_panda_multiple_seq_responses,
):
    """Tests that the mocked_panda_multiple_seq_responses with a number=2 in the
    seq block gives you a SEQ1 and a SEQ2 PV once the ioc starts up, with
    independent values. We also double check a SEQ PV isn't broadcasted."""

    (
        tmp_path,
        child_conn,
        response_handler,
        command_queue,
        test_prefix,
    ) = mocked_panda_multiple_seq_responses

    seq_1_outd1 = await caget(test_prefix + ":SEQ1:TABLE:OUTD2")
    seq_2_outd2 = await caget(test_prefix + ":SEQ2:TABLE:OUTD2")

    assert numpy.array_equal(seq_1_outd1, [0, 0, 1])
    assert numpy.array_equal(seq_2_outd2, [0, 0, 1, 1, 0])

    with pytest.raises(CANothing):
        await caget(test_prefix + ":SEQ:TABLE:OUTD2", timeout=1)


async def test_metadata_parses_into_multiple_pvs(
    mocked_panda_multiple_seq_responses,
):
    # If number=n where n!=1 for the block info of a block
    # then the metadata described for the block needs to be
    # put to each individual PV
    (
        tmp_path,
        child_conn,
        response_handler,
        command_queue,
        test_prefix,
    ) = mocked_panda_multiple_seq_responses

    seq_1_label_metadata = await caget(
        test_prefix + ":SEQ1:LABEL", datatype=DBR_CHAR_STR
    )
    seq_2_label_metadata = await caget(
        test_prefix + ":SEQ2:LABEL", datatype=DBR_CHAR_STR
    )

    assert seq_1_label_metadata == "SeqMetadataLabel"
    assert seq_2_label_metadata == "SeqMetadataLabel"

    # Make sure "*METADATA.LABEL_SEQ": "PcapMetadataLabel", doesn't
    # get parsed into :SEQ:LABEL
    with pytest.raises(CANothing):
        await caget(test_prefix + ":SEQ:LABEL", timeout=1)


async def test_metadata_parses_into_single_pv(mocked_panda_standard_responses):
    (
        tmp_path,
        child_conn,
        response_handler,
        command_queue,
        test_prefix,
    ) = mocked_panda_standard_responses
    pcap_label_metadata = await caget(
        test_prefix + ":PCAP:LABEL", datatype=DBR_CHAR_STR
    )
    assert pcap_label_metadata == "PcapMetadataLabel"

    await caput(
        test_prefix + ":PCAP:LABEL", "SomeOtherPcapMetadataLabel", datatype=DBR_CHAR_STR
    )

    pcap_label_metadata = await caget(
        test_prefix + ":PCAP:LABEL", datatype=DBR_CHAR_STR
    )
    assert pcap_label_metadata == "SomeOtherPcapMetadataLabel"

    # Give the queue time to be put to
    await asyncio.sleep(0.1)

    # Check PCAP:LABEL goes to METADATA_LABEL_PCAP1
    assert command_to_key(
        Put(field="*METADATA.LABEL_PCAP1", value="SomeOtherPcapMetadataLabel")
    ) in multiprocessing_queue_to_list(command_queue)


async def test_metadata_parses_into_multiple_pvs_caput_single_pv(
    mocked_panda_multiple_seq_responses,
):
    (
        tmp_path,
        child_conn,
        response_handler,
        command_queue,
        test_prefix,
    ) = mocked_panda_multiple_seq_responses
    seq_1_label_metadata = await caget(
        test_prefix + ":SEQ1:LABEL", datatype=DBR_CHAR_STR, timeout=TIMEOUT
    )
    seq_2_label_metadata = await caget(
        test_prefix + ":SEQ2:LABEL", datatype=DBR_CHAR_STR, timeout=TIMEOUT
    )

    assert seq_1_label_metadata == "SeqMetadataLabel"
    assert seq_2_label_metadata == "SeqMetadataLabel"

    await caput(
        test_prefix + ":SEQ1:LABEL",
        "SomeOtherSequenceMetadataLabel",
        datatype=DBR_CHAR_STR,
        timeout=TIMEOUT,
    )

    seq_1_label_metadata = await caget(
        test_prefix + ":SEQ1:LABEL", datatype=DBR_CHAR_STR
    )
    seq_2_label_metadata = await caget(
        test_prefix + ":SEQ2:LABEL", datatype=DBR_CHAR_STR
    )

    assert seq_1_label_metadata == "SomeOtherSequenceMetadataLabel"
    assert seq_2_label_metadata == "SeqMetadataLabel"

    # Give the queue time to be put to
    await asyncio.sleep(0.1)

    assert command_to_key(
        Put(field="*METADATA.LABEL_SEQ1", value="SomeOtherSequenceMetadataLabel")
    ) in multiprocessing_queue_to_list(command_queue)


async def test_non_defined_seq_table_can_be_added_to_panda_side(
    mocked_panda_multiple_seq_responses,
):
    (
        tmp_path,
        child_conn,
        response_handler,
        command_queue,
        test_prefix,
    ) = mocked_panda_multiple_seq_responses

    initial_table_outd2 = await caget(
        test_prefix + ":SEQ3:TABLE:OUTD2", timeout=TIMEOUT
    )

    assert list(initial_table_outd2) == []
    try:
        capturing_queue = asyncio.Queue()

        # The mocked panda adds SEQ3 values after some time
        monitor = camonitor(test_prefix + ":SEQ3:TABLE:OUTD2", capturing_queue.put)
        curr_val = await asyncio.wait_for(capturing_queue.get(), TIMEOUT)
        assert list(curr_val) == [0, 0, 1]

    finally:
        monitor.close()

    await caput(test_prefix + ":SEQ3:TABLE:MODE", 1, wait=True)  # TableModeEnum.EDIT
    table_mode = await caget(test_prefix + ":SEQ3:TABLE:MODE", timeout=TIMEOUT)
    assert table_mode == 1

    await caput(
        test_prefix + ":SEQ3:TABLE:REPEATS",
        numpy.array([0, 1, 0]),
        wait=True,
    )
    curr_val = await caget(test_prefix + ":SEQ3:TABLE:REPEATS", timeout=TIMEOUT)

    assert list(curr_val) == [0, 1, 0]

    # TODO Test that the ioc can update the panda values for the enums.
    await caput(test_prefix + ":SEQ3:TABLE:MODE", 2, wait=True)  # TableModeEnum.SUBMIT


async def test_non_defined_seq_table_can_be_added_to_ioc_side(
    mocked_panda_multiple_seq_responses, table_unpacked_data
):
    (
        tmp_path,
        child_conn,
        response_handler,
        command_queue,
        test_prefix,
    ) = mocked_panda_multiple_seq_responses

    for field in table_unpacked_data:
        initial_table_field = await caget(
            test_prefix + ":SEQ4:TABLE:" + field, timeout=TIMEOUT
        )
        assert list(initial_table_field) == []

    initial_table_mode = await caget(test_prefix + ":SEQ4:TABLE:MODE", timeout=TIMEOUT)
    assert initial_table_mode == 0  # TableModeEnum.VIEW

    await caput(test_prefix + ":SEQ4:TABLE:MODE", 1, wait=True)  # TableModeEnum.EDIT
    table_mode = await caget(test_prefix + ":SEQ4:TABLE:MODE", timeout=TIMEOUT)
    assert table_mode == 1

    for field, data in table_unpacked_data.items():
        await caput(
            test_prefix + ":SEQ4:TABLE:" + field,
            data,
            wait=True,
        )

    await caput(test_prefix + ":SEQ4:TABLE:MODE", 2, wait=True)  # TableModeEnum.SUBMIT

    await asyncio.sleep(0.1)
    commands_received = multiprocessing_queue_to_list(command_queue)
    assert (
        command_to_key(
            Put(
                field="SEQ4.TABLE",
                value=[
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
                ],
            )
        )
        in commands_received
    )


async def test_not_including_number_in_metadata_throws_error(
    no_numbered_suffix_to_metadata_responses,
):
    response_handler = ResponseHandler(no_numbered_suffix_to_metadata_responses)
    mocked_client = MockedAsyncioClient(response_handler)

    with pytest.raises(ValueError):
        await introspect_panda(mocked_client)
