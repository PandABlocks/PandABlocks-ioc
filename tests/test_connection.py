"""
For testing that the ioc fails if there's a connection error pre-introspection,
and remains in a disconnected state if the panda disconnects after.
"""

import asyncio
from itertools import chain, repeat

import pytest
from aioca import camonitor
from pandablocks.asyncio import AsyncioClient
from pandablocks.commands import (
    Arm,
    ChangeGroup,
    Disarm,
    GetBlockInfo,
    GetChanges,
    GetFieldInfo,
    GetLine,
    Put,
    TimeFieldInfo,
)
from pandablocks.responses import (
    BitMuxFieldInfo,
    BlockInfo,
    EnumFieldInfo,
)

from fixtures.mocked_panda import (
    TIMEOUT,
    ResponseHandler,
    changes_iterator_wrapper,
    command_to_key,
    create_subprocess_ioc_and_responses,
    respond_with_no_changes,
)
from pandablocks_ioc._connection_status import Statuses
from pandablocks_ioc.ioc import create_softioc


async def test_no_panda_found_connection_error():
    with pytest.raises(ConnectionRefusedError) as exc:
        create_softioc(AsyncioClient("0.0.0.0"), "TEST")
    assert str(exc.value) == "[Errno 111] Connect call failed ('0.0.0.0', 8888)"


@pytest.fixture
def panda_disconnect_responses(table_field_info, table_data_1, table_data_2):
    # The responses return nothing, as the panda disconnects after introspection
    return {
        command_to_key(GetFieldInfo(block="PCAP", extended_metadata=True)): repeat(
            {
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
            }
        ),
        command_to_key(Put(field="PCAP.TRIG_EDGE", value="Falling")): repeat("OK"),
        command_to_key(Put(field="PULSE.DELAY.UNITS", value="min")): repeat("OK"),
        command_to_key(
            Put(field="*METADATA.LABEL_PCAP1", value="SomeOtherPcapMetadataLabel")
        ): repeat("OK"),
        command_to_key(Arm()): repeat("OK"),
        command_to_key(Disarm()): repeat("OK"),
        command_to_key(GetFieldInfo(block="PULSE", extended_metadata=True)): repeat(
            {
                "DELAY": TimeFieldInfo(
                    type="time",
                    units_labels=["min", "s", "ms", "ns"],
                    subtype=None,
                    description="EGU Desc",
                    min_val=8e-06,
                )
            },
        ),
        # DRVL changing from 8e-06 ms to minutes
        command_to_key(GetLine(field="PULSE.DELAY.MIN")): chain(
            ["8e-09"], repeat("1.333333333e-10")
        ),
        command_to_key(GetFieldInfo(block="SEQ", extended_metadata=True)): repeat(
            {"TABLE": table_field_info}
        ),
        command_to_key(GetBlockInfo(skip_description=False)): repeat(
            {
                "PCAP": BlockInfo(number=1, description="PCAP Desc"),
                "SEQ": BlockInfo(number=1, description="SEQ Desc"),
                "PULSE": BlockInfo(number=1, description="PULSE Desc"),
            }
        ),
        # Changes are given at 10Hz, the changes provided are used for many
        # different tests
        command_to_key(GetChanges(group=ChangeGroup.ALL, get_multiline=True)): chain(
            # Initial value of every field
            changes_iterator_wrapper(
                values={
                    "PCAP.TRIG_EDGE": "Falling",
                    "PCAP.GATE": "CLOCK1.OUT",
                    "PCAP.GATE.DELAY": "1",
                    "PCAP.ARM": "0",
                    "*METADATA.LABEL_PCAP1": "PcapMetadataLabel",
                    "PULSE.DELAY": "100",
                    "PULSE.DELAY.UNITS": "ms",
                    "PULSE.DELAY.MIN": "8e-06",
                },
                multiline_values={"SEQ.TABLE": table_data_1},
            ),
            # 0.5 seconds of no changes in case the ioc setup completes
            # before the test starts
            respond_with_no_changes(number_of_iterations=15),
            changes_iterator_wrapper(
                values={
                    "PCAP.TRIG_EDGE": "Either",
                    "PULSE.DELAY.UNITS": "s",
                },
                multiline_values={"SEQ.TABLE": table_data_2},
            ),
            respond_with_no_changes(number_of_iterations=10),
        ),
    }


@pytest.fixture
def mocked_panda_client_disconnects_after_introspection(
    panda_disconnect_responses,
    tmp_path,
    new_random_test_prefix,
    caplog,
    caplog_workaround,
    table_field_info,
    table_fields,
):
    response_handler = ResponseHandler(panda_disconnect_responses)
    yield from create_subprocess_ioc_and_responses(
        response_handler,
        tmp_path,
        new_random_test_prefix,
        caplog,
        caplog_workaround,
        table_field_info,
        table_fields,
    )


async def test_panda_disconnects_after_introspection(
    mocked_panda_client_disconnects_after_introspection,
):
    (
        tmp_path,
        child_conn,
        response_handler,
        command_queue,
        test_prefix,
    ) = mocked_panda_client_disconnects_after_introspection
    try:
        status_queue = asyncio.Queue()
        delay_queue = asyncio.Queue()
        alarm_sevr_queue = asyncio.Queue()
        alarm_stat_queue = asyncio.Queue()

        m1 = camonitor(
            test_prefix + ":Status",
            status_queue.put,
        )
        m2 = camonitor(
            test_prefix + ":PULSE:DELAY",
            delay_queue.put,
        )  # arbitrary field to see alarm states
        m3 = camonitor(
            test_prefix + ":PULSE:DELAY.SEVR",
            alarm_sevr_queue.put,
        )
        m4 = camonitor(
            test_prefix + ":PULSE:DELAY.STAT",
            alarm_stat_queue.put,
        )

        assert (
            await asyncio.wait_for(status_queue.get(), TIMEOUT)
            == Statuses.CONNECTED.value
        )
        assert await asyncio.wait_for(delay_queue.get(), TIMEOUT) == 100.0
        assert await asyncio.wait_for(alarm_stat_queue.get(), TIMEOUT) == 0
        assert await asyncio.wait_for(alarm_sevr_queue.get(), TIMEOUT) == 0

        # The panda disconnects after introspection
        assert (
            await asyncio.wait_for(status_queue.get(), TIMEOUT)
            == Statuses.DISCONNECTED.value
        )

        # Once PythonSoftIOC issue #53 is fixed we can set the
        # alarm states of out records
        # assert await caget(test_prefix + ":PULSE:DELAY.STAT") == 20
        # assert await caget(test_prefix + ":PULSE:DELAY.SEVR") == 2

    finally:
        m1.close()
        m2.close()
        m3.close()
        m4.close()
