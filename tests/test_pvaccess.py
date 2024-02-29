import asyncio
import collections
from typing import OrderedDict

import numpy
from numpy import ndarray
from p4p.client.asyncio import Context

from fixtures.mocked_panda import TIMEOUT
from pandablocks_ioc._types import EpicsName


async def test_table_column_info(
    mocked_panda_multiple_seq_responses,
    table_unpacked_data: OrderedDict[EpicsName, ndarray],
):
    """Test that the table columns have the expected PVAccess information in the
    right order"""
    (
        tmp_path,
        child_conn,
        response_handler,
        command_queue,
        test_prefix,
    ) = mocked_panda_multiple_seq_responses

    ctxt = Context("pva", nt=False)

    try:
        capturing_queue: asyncio.Queue = asyncio.Queue()
        monitor = ctxt.monitor(test_prefix + ":SEQ1:TABLE", capturing_queue.put)
        table_value = await asyncio.wait_for(capturing_queue.get(), timeout=TIMEOUT)
    finally:
        monitor.close()

    for (actual_name, actual_value), (expected_name, expected_value) in zip(
        table_value.todict(wrapper=collections.OrderedDict)["value"].items(),
        table_unpacked_data.items(),
    ):
        assert actual_name.upper() == expected_name, (
            f"Order of columns incorrect expected: {expected_name} "
            f"Actual: {actual_name.upper()}"
        )
        numpy.testing.assert_array_equal(actual_value, expected_value)
