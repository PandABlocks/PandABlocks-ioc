# Tests for the _hdf_ioc.py file

import asyncio
import logging
import os
from asyncio import CancelledError
from collections import deque
from multiprocessing.connection import Connection
from pathlib import Path
from typing import AsyncGenerator, Generator

import h5py
import numpy
import pytest
import pytest_asyncio
from aioca import DBR_CHAR_STR, CANothing, caget, caput
from mock.mock import AsyncMock, MagicMock, patch
from pandablocks.asyncio import AsyncioClient
from pandablocks.responses import (
    EndData,
    EndReason,
    FieldCapture,
    FrameData,
    ReadyData,
    StartData,
)
from softioc import asyncio_dispatcher, builder, softioc

from fixtures.mocked_panda import (
    TIMEOUT,
    MockedAsyncioClient,
    Rows,
    append_random_uppercase,
    custom_logger,
    enable_codecov_multiprocess,
    get_multiprocessing_context,
    select_and_recv,
)
from pandablocks_ioc._hdf_ioc import (
    CaptureMode,
    Dataset,
    DatasetNameCache,
    HDF5Buffer,
    HDF5RecordController,
    NumCapturedSetter,
)
from pandablocks_ioc._types import EpicsName

NAMESPACE_PREFIX = "HDF-RECORD-PREFIX"


@pytest.fixture
def new_random_hdf5_prefix():
    test_prefix = append_random_uppercase(NAMESPACE_PREFIX)
    hdf5_test_prefix = test_prefix + ":DATA"
    return test_prefix, hdf5_test_prefix


DUMP_FIELDS = [
    FieldCapture(
        name="PCAP.BITS2",
        type=numpy.dtype("uint32"),
        capture="Value",
        scale=1,
        offset=0,
        units="",
    ),
    FieldCapture(
        name="COUNTER1.OUT",
        type=numpy.dtype("float64"),
        capture="Min",
        scale=1,
        offset=0,
        units="",
    ),
    FieldCapture(
        name="COUNTER1.OUT",
        type=numpy.dtype("float64"),
        capture="Max",
        scale=1,
        offset=0,
        units="",
    ),
    FieldCapture(
        name="COUNTER3.OUT",
        type=numpy.dtype("float64"),
        capture="Value",
        scale=1,
        offset=0,
        units="",
    ),
    FieldCapture(
        name="PCAP.TS_START",
        type=numpy.dtype("float64"),
        capture="Value",
        scale=8e-09,
        offset=0,
        units="s",
    ),
    FieldCapture(
        name="COUNTER1.OUT",
        type=numpy.dtype("float64"),
        capture="Mean",
        scale=1,
        offset=0,
        units="",
    ),
    FieldCapture(
        name="COUNTER2.OUT",
        type=numpy.dtype("float64"),
        capture="Mean",
        scale=1,
        offset=0,
        units="",
    ),
]


@pytest_asyncio.fixture
def slow_dump_expected():
    yield [
        ReadyData(),
        StartData(DUMP_FIELDS, 0, "Scaled", "Framed", 52, None, None, None),
        FrameData(Rows([0, 1, 1, 3, 5.6e-08, 1, 2])),
        FrameData(Rows([8, 2, 2, 6, 1.000000056, 2, 4])),
        FrameData(Rows([0, 3, 3, 9, 2.000000056, 3, 6])),
        FrameData(Rows([8, 4, 4, 12, 3.000000056, 4, 8])),
        FrameData(Rows([0, 5, 5, 15, 4.000000056, 5, 10])),
        EndData(5, EndReason.DISARMED),
    ]


@pytest_asyncio.fixture
def fast_dump_expected():
    yield [
        ReadyData(),
        StartData(DUMP_FIELDS, 0, "Scaled", "Framed", 52, None, None, None),
        FrameData(
            Rows(
                [0, 1, 1, 3, 5.6e-08, 1, 2],
                [0, 2, 2, 6, 0.010000056, 2, 4],
                [8, 3, 3, 9, 0.020000056, 3, 6],
                [8, 4, 4, 12, 0.030000056, 4, 8],
                [8, 5, 5, 15, 0.040000056, 5, 10],
                [8, 6, 6, 18, 0.050000056, 6, 12],
                [8, 7, 7, 21, 0.060000056, 7, 14],
                [8, 8, 8, 24, 0.070000056, 8, 16],
                [8, 9, 9, 27, 0.080000056, 9, 18],
                [8, 10, 10, 30, 0.090000056, 10, 20],
            )
        ),
        FrameData(
            Rows(
                [0, 11, 11, 33, 0.100000056, 11, 22],
                [8, 12, 12, 36, 0.110000056, 12, 24],
                [8, 13, 13, 39, 0.120000056, 13, 26],
                [8, 14, 14, 42, 0.130000056, 14, 28],
                [8, 15, 15, 45, 0.140000056, 15, 30],
                [8, 16, 16, 48, 0.150000056, 16, 32],
                [8, 17, 17, 51, 0.160000056, 17, 34],
                [8, 18, 18, 54, 0.170000056, 18, 36],
                [8, 19, 19, 57, 0.180000056, 19, 38],
                [0, 20, 20, 60, 0.190000056, 20, 40],
                [8, 21, 21, 63, 0.200000056, 21, 42],
            )
        ),
        FrameData(
            Rows(
                [8, 22, 22, 66, 0.210000056, 22, 44],
                [8, 23, 23, 69, 0.220000056, 23, 46],
                [8, 24, 24, 72, 0.230000056, 24, 48],
                [8, 25, 25, 75, 0.240000056, 25, 50],
                [8, 26, 26, 78, 0.250000056, 26, 52],
                [8, 27, 27, 81, 0.260000056, 27, 54],
                [8, 28, 28, 84, 0.270000056, 28, 56],
                [0, 29, 29, 87, 0.280000056, 29, 58],
                [8, 30, 30, 90, 0.290000056, 30, 60],
                [8, 31, 31, 93, 0.300000056, 31, 62],
            )
        ),
        FrameData(
            Rows(
                [8, 32, 32, 96, 0.310000056, 32, 64],
                [8, 33, 33, 99, 0.320000056, 33, 66],
                [8, 34, 34, 102, 0.330000056, 34, 68],
                [8, 35, 35, 105, 0.340000056, 35, 70],
                [8, 36, 36, 108, 0.350000056, 36, 72],
                [8, 37, 37, 111, 0.360000056, 37, 74],
                [0, 38, 38, 114, 0.370000056, 38, 76],
                [8, 39, 39, 117, 0.380000056, 39, 78],
                [8, 40, 40, 120, 0.390000056, 40, 80],
                [8, 41, 41, 123, 0.400000056, 41, 82],
            )
        ),
        FrameData(
            Rows(
                [8, 42, 42, 126, 0.410000056, 42, 84],
                [8, 43, 43, 129, 0.420000056, 43, 86],
                [8, 44, 44, 132, 0.430000056, 44, 88],
                [8, 45, 45, 135, 0.440000056, 45, 90],
                [8, 46, 46, 138, 0.450000056, 46, 92],
                [0, 47, 47, 141, 0.460000056, 47, 94],
                [8, 48, 48, 144, 0.470000056, 48, 96],
                [8, 49, 49, 147, 0.480000056, 49, 98],
                [8, 50, 50, 150, 0.490000056, 50, 100],
                [8, 51, 51, 153, 0.500000056, 51, 102],
            )
        ),
        FrameData(
            Rows(
                [8, 52, 52, 156, 0.510000056, 52, 104],
                [8, 53, 53, 159, 0.520000056, 53, 106],
                [8, 54, 54, 162, 0.530000056, 54, 108],
                [8, 55, 55, 165, 0.540000056, 55, 110],
                [0, 56, 56, 168, 0.550000056, 56, 112],
                [8, 57, 57, 171, 0.560000056, 57, 114],
                [8, 58, 58, 174, 0.570000056, 58, 116],
            )
        ),
        EndData(58, EndReason.OK),
    ]


@pytest_asyncio.fixture
async def hdf5_controller(
    clear_records: None, standard_responses, new_random_hdf5_prefix
) -> AsyncGenerator:
    """Construct an HDF5 controller, ensuring we delete all records before
    and after the test runs, as well as ensuring the sockets opened in the HDF5
    controller are closed"""

    test_prefix, hdf5_test_prefix = new_random_hdf5_prefix

    dataset_name_cache = {
        EpicsName("COUNTER1:OUT"): Dataset("some_other_dataset_name", "Value"),
    }

    hdf5_controller = HDF5RecordController(
        AsyncioClient("localhost"), dataset_name_cache, test_prefix
    )

    # When using tests w/o CA, need to manually set _directory_exists to 1
    hdf5_controller._directory_exists_record.set(1)

    yield hdf5_controller
    # Give time for asyncio to fully close its connections
    await asyncio.sleep(0)


def subprocess_func(
    namespace_prefix: str, standard_responses, child_conn: Connection
) -> None:
    """Function to start the HDF5 IOC"""
    enable_codecov_multiprocess()

    async def wrapper():
        builder.SetDeviceName(namespace_prefix)
        client = MockedAsyncioClient(standard_responses)
        HDF5RecordController(client, {}, namespace_prefix)
        dispatcher = asyncio_dispatcher.AsyncioDispatcher()
        builder.LoadDatabase()
        softioc.iocInit(dispatcher)
        child_conn.send("R")

        # Leave this coroutine running until it's torn down by pytest
        await asyncio.Event().wait()

    custom_logger()
    asyncio.run(wrapper())


@pytest_asyncio.fixture
def hdf5_subprocess_ioc_no_logging_check(
    caplog, caplog_workaround, standard_responses, new_random_hdf5_prefix, clear_records
) -> Generator:
    """Create an instance of HDF5 class in its own subprocess, then start the IOC.
    Note you probably want to use `hdf5_subprocess_ioc` instead."""

    test_prefix, hdf5_test_prefix = new_random_hdf5_prefix

    ctx = get_multiprocessing_context()
    parent_conn, child_conn = ctx.Pipe()
    p = ctx.Process(
        target=subprocess_func, args=(test_prefix, standard_responses, child_conn)
    )
    try:
        p.start()
        select_and_recv(parent_conn)  # Wait for IOC to start up
        yield test_prefix, hdf5_test_prefix
    finally:
        child_conn.close()
        parent_conn.close()
        p.terminate()
        p.join(timeout=TIMEOUT)
        # Should never take anywhere near 10 seconds to terminate, it's just there
        # to ensure the test doesn't hang indefinitely during cleanup


@pytest_asyncio.fixture
def hdf5_subprocess_ioc(
    caplog, caplog_workaround, standard_responses, new_random_hdf5_prefix, clear_records
) -> Generator:
    """Create an instance of HDF5 class in its own subprocess, then start the IOC.
    When finished check logging logged no messages of WARNING or higher level."""

    test_prefix, hdf5_test_prefix = new_random_hdf5_prefix

    with caplog.at_level(logging.WARNING):
        with caplog_workaround():
            ctx = get_multiprocessing_context()
            parent_conn, child_conn = ctx.Pipe()
            p = ctx.Process(
                target=subprocess_func,
                args=(test_prefix, standard_responses, child_conn),
            )
            try:
                p.start()
                select_and_recv(parent_conn)  # Wait for IOC to start up
                yield test_prefix, hdf5_test_prefix
            finally:
                child_conn.close()
                parent_conn.close()
                p.terminate()
                p.join(timeout=TIMEOUT)
                # Should never take anywhere near 10 seconds to terminate,
                # it's just there to ensure the test doesn't hang indefinitely
                # during cleanup

    # We expect all tests to pass without warnings (or worse) logged.
    assert (
        len(caplog.messages) == 0
    ), f"At least one warning/error/exception logged during test: {caplog.records}"


async def test_hdf5_ioc(hdf5_subprocess_ioc):
    """Run the HDF5 module as its own IOC and check the expected records are created,
    with some default values checked"""

    test_prefix, hdf5_test_prefix = hdf5_subprocess_ioc

    val = await caget(hdf5_test_prefix + ":HDFDirectory", datatype=DBR_CHAR_STR)

    # Default value of longStringOut is an array of a single NULL byte
    assert val == ""

    # Mix and match between CamelCase and UPPERCASE to check aliases work
    val = await caget(hdf5_test_prefix + ":HDF_FILE_NAME", datatype=DBR_CHAR_STR)
    assert val == ""

    val = await caget(hdf5_test_prefix + ":NumCapture")
    assert val == 0

    val = await caget(hdf5_test_prefix + ":FlushPeriod")
    assert val == 1.0

    val = await caget(hdf5_test_prefix + ":CAPTURE")
    assert val == 0

    val = await caget(hdf5_test_prefix + ":Status", datatype=DBR_CHAR_STR)
    assert val == "OK"

    val = await caget(hdf5_test_prefix + ":CreateDirectory")
    assert val == 0

    val = await caget(hdf5_test_prefix + ":DirectoryExists")
    assert val == 0


async def test_hdf5_ioc_parameter_validate_works(
    hdf5_subprocess_ioc_no_logging_check, tmp_path
):
    """Run the HDF5 module as its own IOC and check the _parameter_validate method
    does not stop updates, then stops when capture record is changed"""

    test_prefix, hdf5_test_prefix = hdf5_subprocess_ioc_no_logging_check

    # EPICS bug means caputs always appear to succeed, so do a caget to prove it worked
    await caput(
        hdf5_test_prefix + ":HDFDirectory",
        str(tmp_path),
        datatype=DBR_CHAR_STR,
        wait=True,
    )
    val = await caget(hdf5_test_prefix + ":HDFDirectory", datatype=DBR_CHAR_STR)
    assert val == str(tmp_path)

    await caput(
        hdf5_test_prefix + ":HDFFileName", "name.h5", wait=True, datatype=DBR_CHAR_STR
    )
    val = await caget(hdf5_test_prefix + ":HDFFileName", datatype=DBR_CHAR_STR)
    assert val == "name.h5"

    await caput(hdf5_test_prefix + ":Capture", 1, wait=True)
    assert await caget(hdf5_test_prefix + ":Capture") == 1

    with pytest.raises(CANothing):
        await caput(
            hdf5_test_prefix + ":HDFFullFilePath",
            "/second/path/name.h5",
            wait=True,
            datatype=DBR_CHAR_STR,
        )
    val = await caget(hdf5_test_prefix + ":HDFFullFilePath", datatype=DBR_CHAR_STR)
    assert val == str(tmp_path) + "/name.h5"  # put should have been stopped


@pytest.mark.parametrize(
    "create_depth, path, expect_exists, restrict_permissions",
    [
        (0, ".", True, False),
        (0, "panda_test1", False, False),
        (-2, "panda_test2", True, False),
        (-1, "panda_test3/depth_2", False, False),
        (1, "panda_test4/depth_2", True, False),
        (0, ".", False, True),
        (1, "panda_test5", False, True),
        (-1, "panda_test6", False, True),
        (10, "panda_test7", False, False),
    ],
)
async def test_hdf5_dir_creation(
    hdf5_subprocess_ioc,
    tmp_path: Path,
    create_depth: int,
    path: str,
    expect_exists: bool,
    restrict_permissions: bool,
):
    """Test to see if directory creation/exists works as expected"""

    if restrict_permissions:
        # Artificially restrict perms for temp folder to simulate perm issues.
        tmp_path.chmod(0o444)

    _, hdf5_test_prefix = hdf5_subprocess_ioc

    target_path = str(tmp_path / path)

    await caput(
        hdf5_test_prefix + ":CreateDirectory",
        create_depth,
        wait=True,
    )
    await caput(
        hdf5_test_prefix + ":HDFDirectory",
        target_path,
        datatype=DBR_CHAR_STR,
        wait=True,
    )
    exists = await caget(hdf5_test_prefix + ":DirectoryExists")

    assert (exists > 0) == expect_exists
    if expect_exists:
        assert os.path.exists(target_path)
        assert os.access(target_path, os.W_OK)

    if restrict_permissions:
        # Put back default permissions
        tmp_path.chmod(0o700)


async def test_hdf5_file_writing_no_dir(hdf5_subprocess_ioc, tmp_path: Path, caplog):
    """Test that if dir doesn't exist, HDF file writing fails with a runtime error"""
    test_prefix, hdf5_test_prefix = hdf5_subprocess_ioc

    test_dir = tmp_path
    test_filename = "test.h5"
    await caput(
        hdf5_test_prefix + ":HDFDirectory",
        str(test_dir / "panda_test1"),
        wait=True,
        datatype=DBR_CHAR_STR,
    )

    exists = await caget(hdf5_test_prefix + ":DirectoryExists")
    assert exists == 0

    await caput(
        hdf5_test_prefix + ":HDFFileName", "name.h5", wait=True, datatype=DBR_CHAR_STR
    )
    await caput(
        hdf5_test_prefix + ":HDFFileName",
        test_filename,
        wait=True,
        timeout=TIMEOUT,
        datatype=DBR_CHAR_STR,
    )

    val = await caget(hdf5_test_prefix + ":HDFFullFilePath", datatype=DBR_CHAR_STR)
    assert val == "/".join([str(tmp_path), "panda_test1", test_filename])

    await caput(hdf5_test_prefix + ":NumCapture", 1, wait=True, timeout=TIMEOUT)

    await caput(hdf5_test_prefix + ":Capture", 1, wait=True, timeout=TIMEOUT)

    val = await caget(hdf5_test_prefix + ":Status", datatype=DBR_CHAR_STR)
    assert val == "Capture disabled, unexpected exception"


@pytest.mark.parametrize("num_capture", [1, 1000, 10000])
async def test_hdf5_file_writing_first_n(
    hdf5_subprocess_ioc, tmp_path: Path, caplog, num_capture
):
    """Test that an HDF5 file is written when Capture is enabled"""

    test_prefix, hdf5_test_prefix = hdf5_subprocess_ioc

    val = await caget(hdf5_test_prefix + ":CaptureMode")
    assert val == CaptureMode.FIRST_N.value

    test_dir = tmp_path
    test_filename = "test.h5"
    await caput(
        hdf5_test_prefix + ":HDFDirectory",
        str(test_dir),
        wait=True,
        datatype=DBR_CHAR_STR,
    )
    val = await caget(hdf5_test_prefix + ":HDFDirectory", datatype=DBR_CHAR_STR)
    assert val == str(test_dir)

    await caput(
        hdf5_test_prefix + ":HDFFileName", "name.h5", wait=True, datatype=DBR_CHAR_STR
    )
    val = await caget(hdf5_test_prefix + ":HDFFileName", datatype=DBR_CHAR_STR)
    assert val == "name.h5"

    await caput(
        hdf5_test_prefix + ":HDFFileName",
        test_filename,
        wait=True,
        timeout=TIMEOUT,
        datatype=DBR_CHAR_STR,
    )
    val = await caget(hdf5_test_prefix + ":HDFFileName", datatype=DBR_CHAR_STR)
    assert val == test_filename

    val = await caget(hdf5_test_prefix + ":HDFFullFilePath", datatype=DBR_CHAR_STR)
    assert val == "/".join([str(tmp_path), test_filename])

    # Only a single FrameData in the example data
    assert await caget(hdf5_test_prefix + ":NumCapture") == 0
    await caput(
        hdf5_test_prefix + ":NumCapture", num_capture, wait=True, timeout=TIMEOUT
    )
    assert await caget(hdf5_test_prefix + ":NumCapture") == num_capture

    await caput(hdf5_test_prefix + ":Capture", 1, wait=True, timeout=TIMEOUT)
    assert await caget(hdf5_test_prefix + ":NumReceived") <= num_capture

    await asyncio.sleep(1)
    # Capture should have closed by itself
    assert await caget(hdf5_test_prefix + ":Capture") == 0

    assert await caget(hdf5_test_prefix + ":NumReceived") == num_capture
    assert await caget(hdf5_test_prefix + ":NumCaptured") == num_capture
    # Confirm file contains data we expect
    with h5py.File(tmp_path / test_filename, "r") as hdf_file:
        assert list(hdf_file) == [
            "COUNTER1.OUT.Max",
            "COUNTER1.OUT.Mean",
            "COUNTER1.OUT.Min",
            "COUNTER2.OUT.Mean",
            "COUNTER3.OUT.Value",
            "PCAP.BITS2.Value",
            "PCAP.SAMPLES.Value",
            "PCAP.TS_START.Value",
        ]

        assert len(hdf_file["/COUNTER1.OUT.Max"]) == num_capture

    assert (
        await caget(hdf5_test_prefix + ":Status", datatype=DBR_CHAR_STR)
        == "Requested number of frames captured"
    )


@pytest.mark.parametrize("num_capture", [1, 1000, 10000])
async def test_hdf5_file_writing_last_n_endreason_not_ok(
    hdf5_subprocess_ioc, tmp_path: Path, caplog, num_capture
):
    """Test that an HDF5 file is written when Capture is enabled"""

    test_prefix, hdf5_test_prefix = hdf5_subprocess_ioc

    val = await caget(hdf5_test_prefix + ":CaptureMode")
    assert val == CaptureMode.FIRST_N.value
    await caput(hdf5_test_prefix + ":CaptureMode", 1, wait=True)
    val = await caget(hdf5_test_prefix + ":CaptureMode")
    assert val == CaptureMode.LAST_N.value

    test_dir = tmp_path
    test_filename = "test.h5"
    await caput(
        hdf5_test_prefix + ":HDFDirectory",
        str(test_dir),
        wait=True,
        datatype=DBR_CHAR_STR,
    )
    val = await caget(hdf5_test_prefix + ":HDFDirectory", datatype=DBR_CHAR_STR)
    assert val == str(test_dir)

    await caput(
        hdf5_test_prefix + ":HDFFileName", "name.h5", wait=True, datatype=DBR_CHAR_STR
    )
    val = await caget(hdf5_test_prefix + ":HDFFileName", datatype=DBR_CHAR_STR)
    assert val == "name.h5"

    await caput(
        hdf5_test_prefix + ":HDFFileName",
        test_filename,
        wait=True,
        timeout=TIMEOUT,
        datatype=DBR_CHAR_STR,
    )
    val = await caget(hdf5_test_prefix + ":HDFFileName", datatype=DBR_CHAR_STR)
    assert val == test_filename

    val = await caget(hdf5_test_prefix + ":HDFFullFilePath", datatype=DBR_CHAR_STR)
    assert val == "/".join([str(tmp_path), test_filename])

    # Only a single FrameData in the example data
    assert await caget(hdf5_test_prefix + ":NumCapture") == 0
    await caput(
        hdf5_test_prefix + ":NumCapture", num_capture, wait=True, timeout=TIMEOUT
    )
    assert await caget(hdf5_test_prefix + ":NumCapture") == num_capture

    # Initially Status should be "Dir exists and is writable"
    val = await caget(hdf5_test_prefix + ":Status", datatype=DBR_CHAR_STR)
    assert val == "Dir exists and is writable"

    await caput(hdf5_test_prefix + ":Capture", 1, wait=True, timeout=TIMEOUT)

    await asyncio.sleep(1)
    # Capture should have closed by itself
    assert await caget(hdf5_test_prefix + ":Capture") == 0

    val = await caget(hdf5_test_prefix + ":Status", datatype=DBR_CHAR_STR)
    assert (
        val == "Stopped capturing with reason EndReason.DISARMED, "
        "skipping writing of buffered frames"
    )

    # We received all 10000 frames even if we asked to capture fewer.
    assert await caget(hdf5_test_prefix + ":NumReceived") == 10000

    # We didn't write any frames since the endreason was `EndReason.DISARMED`,
    # not endreason `EndReason.OK`
    assert await caget(hdf5_test_prefix + ":NumCaptured") == 0

    # Confirm no data was written
    assert not (tmp_path / test_filename).exists()


@pytest_asyncio.fixture
def differently_sized_framedata():
    yield [
        ReadyData(),
        StartData(DUMP_FIELDS, 0, "Scaled", "Framed", 52, None, None, None),
        FrameData(
            numpy.array(
                [
                    [0, 1, 1, 3, 5.6e-08, 1, 2],
                    [0, 2, 2, 6, 0.010000056, 2, 4],
                    [8, 3, 3, 9, 0.020000056, 3, 6],
                    [8, 4, 4, 12, 0.030000056, 4, 8],
                    [8, 5, 5, 15, 0.040000056, 5, 10],
                    [8, 6, 6, 18, 0.050000056, 6, 12],
                    [8, 7, 7, 21, 0.060000056, 7, 14],
                    [8, 8, 8, 24, 0.070000056, 8, 16],
                    [8, 9, 9, 27, 0.080000056, 9, 18],
                    [8, 10, 10, 30, 0.090000056, 10, 20],
                ]
            )
        ),
        FrameData(
            numpy.array(
                [
                    [0, 11, 11, 33, 0.100000056, 11, 22],
                    [8, 12, 12, 36, 0.110000056, 12, 24],
                    [8, 13, 13, 39, 0.120000056, 13, 26],
                    [8, 14, 14, 42, 0.130000056, 14, 28],
                    [8, 15, 15, 45, 0.140000056, 15, 30],
                    [8, 16, 16, 48, 0.150000056, 16, 32],
                    [8, 17, 17, 51, 0.160000056, 17, 34],
                    [8, 18, 18, 54, 0.170000056, 18, 36],
                    [8, 19, 19, 57, 0.180000056, 19, 38],
                    [0, 20, 20, 60, 0.190000056, 20, 40],
                    [8, 21, 21, 63, 0.200000056, 21, 42],
                ]
            )
        ),
        FrameData(
            numpy.array(
                [
                    [8, 22, 22, 66, 0.210000056, 22, 44],
                    [8, 23, 23, 69, 0.220000056, 23, 46],
                    [8, 24, 24, 72, 0.230000056, 24, 48],
                    [8, 25, 25, 75, 0.240000056, 25, 50],
                    [8, 26, 26, 78, 0.250000056, 26, 52],
                    [8, 27, 27, 81, 0.260000056, 27, 54],
                    [8, 28, 28, 84, 0.270000056, 28, 56],
                    [0, 29, 29, 87, 0.280000056, 29, 58],
                    [8, 30, 30, 90, 0.290000056, 30, 60],
                    [8, 31, 31, 93, 0.300000056, 31, 62],
                ]
            )
        ),
        FrameData(
            numpy.array(
                [
                    [8, 32, 32, 96, 0.310000056, 32, 64],
                    [8, 33, 33, 99, 0.320000056, 33, 66],
                    [8, 34, 34, 102, 0.330000056, 34, 68],
                    [8, 35, 35, 105, 0.340000056, 35, 70],
                    [8, 36, 36, 108, 0.350000056, 36, 72],
                    [8, 37, 37, 111, 0.360000056, 37, 74],
                    [0, 38, 38, 114, 0.370000056, 38, 76],
                    [8, 39, 39, 117, 0.380000056, 39, 78],
                    [8, 40, 40, 120, 0.390000056, 40, 80],
                    [8, 41, 41, 123, 0.400000056, 41, 82],
                ]
            )
        ),
        FrameData(
            numpy.array(
                [
                    [8, 42, 42, 126, 0.410000056, 42, 84],
                    [8, 43, 43, 129, 0.420000056, 43, 86],
                    [8, 44, 44, 132, 0.430000056, 44, 88],
                    [8, 45, 45, 135, 0.440000056, 45, 90],
                    [8, 46, 46, 138, 0.450000056, 46, 92],
                    [0, 47, 47, 141, 0.460000056, 47, 94],
                    [8, 48, 48, 144, 0.470000056, 48, 96],
                    [8, 49, 49, 147, 0.480000056, 49, 98],
                    [8, 50, 50, 150, 0.490000056, 50, 100],
                    [8, 51, 51, 153, 0.500000056, 51, 102],
                ]
            )
        ),
        FrameData(
            numpy.array(
                [
                    [8, 52, 52, 156, 0.510000056, 52, 104],
                    [8, 53, 53, 159, 0.520000056, 53, 106],
                    [8, 54, 54, 162, 0.530000056, 54, 108],
                    [8, 55, 55, 165, 0.540000056, 55, 110],
                    [0, 56, 56, 168, 0.550000056, 56, 112],
                    [8, 57, 57, 171, 0.560000056, 57, 114],
                    [8, 58, 58, 174, 0.570000056, 58, 116],
                ]
            )
        ),
        EndData(58, EndReason.OK),
    ]


def test_hdf_buffer_forever(differently_sized_framedata, tmp_path):
    filepath = str(tmp_path / "test_file.h5")
    status_output = []
    num_received_output = []
    num_captured_output = []
    frames_written_to_file = []
    num_captured_output = []
    num_captured_setter_pipeline = NumCapturedSetter(num_captured_output.append)
    buffer = HDF5Buffer(
        CaptureMode.FOREVER,
        filepath,
        21,
        status_output.append,
        num_received_output.append,
        num_captured_setter_pipeline,
        {},
    )
    buffer.put_data_to_file = frames_written_to_file.append

    for data in differently_sized_framedata:
        buffer.handle_data(data)

    assert buffer.number_of_received_rows == 58
    assert not buffer.finish_capturing

    differently_sized_framedata[-1] = EndData(58, EndReason.MANUALLY_STOPPED)

    for data in differently_sized_framedata:
        buffer.handle_data(data)

    assert buffer.number_of_received_rows == 116
    assert buffer.finish_capturing

    assert len(frames_written_to_file) == 14
    assert (
        sum(
            len(frame.data)
            for frame in frames_written_to_file
            if isinstance(frame, FrameData)
        )
        == 116
    )


def test_hdf_buffer_last_n(differently_sized_framedata, tmp_path):
    filepath = str(tmp_path / "test_file.h5")
    status_output = []
    num_received_output = []
    num_captured_output = []
    frames_written_to_file = []
    num_captured_output = []
    num_captured_setter_pipeline = NumCapturedSetter(num_captured_output.append)
    buffer = HDF5Buffer(
        CaptureMode.LAST_N,
        filepath,
        21,
        status_output.append,
        num_received_output.append,
        num_captured_setter_pipeline,
        {},
    )
    buffer.put_data_to_file = frames_written_to_file.append

    for data in differently_sized_framedata:
        buffer.handle_data(data)

    assert buffer.number_of_received_rows == 58
    assert buffer.number_of_rows_in_circular_buffer == 21

    expected_cut_off_data = deque(
        [
            FrameData(
                numpy.array(
                    [
                        [0, 38, 38, 114, 0.370000056, 38, 76],
                        [8, 39, 39, 117, 0.380000056, 39, 78],
                        [8, 40, 40, 120, 0.390000056, 40, 80],
                        [8, 41, 41, 123, 0.400000056, 41, 82],
                    ]
                )
            ),
            FrameData(
                numpy.array(
                    [
                        [8, 42, 42, 126, 0.410000056, 42, 84],
                        [8, 43, 43, 129, 0.420000056, 43, 86],
                        [8, 44, 44, 132, 0.430000056, 44, 88],
                        [8, 45, 45, 135, 0.440000056, 45, 90],
                        [8, 46, 46, 138, 0.450000056, 46, 92],
                        [0, 47, 47, 141, 0.460000056, 47, 94],
                        [8, 48, 48, 144, 0.470000056, 48, 96],
                        [8, 49, 49, 147, 0.480000056, 49, 98],
                        [8, 50, 50, 150, 0.490000056, 50, 100],
                        [8, 51, 51, 153, 0.500000056, 51, 102],
                    ]
                )
            ),
            FrameData(
                numpy.array(
                    [
                        [8, 52, 52, 156, 0.510000056, 52, 104],
                        [8, 53, 53, 159, 0.520000056, 53, 106],
                        [8, 54, 54, 162, 0.530000056, 54, 108],
                        [8, 55, 55, 165, 0.540000056, 55, 110],
                        [0, 56, 56, 168, 0.550000056, 56, 112],
                        [8, 57, 57, 171, 0.560000056, 57, 114],
                        [8, 58, 58, 174, 0.570000056, 58, 116],
                    ]
                )
            ),
        ]
    )

    output_frames = [
        frame_data
        for frame_data in frames_written_to_file
        if isinstance(frame_data, FrameData)
    ]
    for expected_frame, output_frame in zip(expected_cut_off_data, output_frames):
        numpy.testing.assert_array_equal(expected_frame.data, output_frame.data)


def test_hdf_buffer_last_n_large_data(tmp_path):
    filepath = str(tmp_path / "test_file.h5")
    status_output = []
    num_received_output = []
    num_captured_output = []
    frames_written_to_file = []
    num_captured_setter_pipeline = NumCapturedSetter(num_captured_output.append)
    buffer = HDF5Buffer(
        CaptureMode.LAST_N,
        filepath,
        25000,
        status_output.append,
        num_received_output.append,
        num_captured_setter_pipeline,
        {},
    )
    buffer.put_data_to_file = frames_written_to_file.append

    large_data = [
        ReadyData(),
        StartData([], 0, "Scaled", "Framed", 52, None, None, None),
        FrameData(numpy.zeros(25000)),
        FrameData(numpy.zeros(25000)),
        FrameData(numpy.zeros(25000)),
        FrameData(numpy.zeros(25000)),
        FrameData(numpy.zeros(25000)),
        FrameData(numpy.append(numpy.zeros(15000), numpy.arange(1, 10001))),
        EndData(150000, EndReason.OK),
    ]

    for data in large_data:
        buffer.handle_data(data)

    assert buffer.number_of_received_rows == 150000
    assert buffer.number_of_rows_in_circular_buffer == 25000

    expected_output = [
        StartData([], 0, "Scaled", "Framed", 52, None, None, None),
        FrameData(numpy.append(numpy.zeros(15000), numpy.arange(1, 10001))),
        EndData(150000, EndReason.OK),
    ]

    output_frames = [
        frame_data
        for frame_data in frames_written_to_file
        if isinstance(frame_data, FrameData)
    ]
    assert len(output_frames) == 1
    numpy.testing.assert_array_equal(output_frames[0].data, expected_output[1].data)


def test_hdf_parameter_validate_not_capturing(hdf5_controller: HDF5RecordController):
    """Test that parameter_validate allows record updates when capturing is off"""

    hdf5_controller._capture_control_record = MagicMock()
    # Default return value for capturing off, allowing validation method to pass
    hdf5_controller._capture_control_record.get = MagicMock(return_value=0)
    hdf5_controller._capture_control_record.get.return_value = 0

    # Don't care about the record being validated, just mock it
    assert hdf5_controller._parameter_validate(MagicMock(), None) is True


def test_hdf_parameter_validate_capturing(hdf5_controller: HDF5RecordController):
    """Test that parameter_validate stops record updates when capturing is on"""

    hdf5_controller._capture_control_record = MagicMock()
    # Default return value for capturing off, allowing validation method to pass
    hdf5_controller._capture_control_record.get = MagicMock(return_value=0)
    hdf5_controller._capture_control_record.get.return_value = 1

    # Don't care about the record being validated, just mock it
    assert hdf5_controller._parameter_validate(MagicMock(), None) is False


@patch("pandablocks_ioc._hdf_ioc.stop_pipeline")
@patch("pandablocks_ioc._hdf_ioc.create_default_pipeline")
async def test_handle_data(
    mock_create_default_pipeline: MagicMock,
    mock_stop_pipeline: MagicMock,
    hdf5_controller: HDF5RecordController,
    slow_dump_expected,
):
    """Test that _handle_hdf5_data can process a normal stream of Data"""

    async def mock_data(scaled, flush_period):
        for item in slow_dump_expected:
            yield item

    # Set up all the mocks
    hdf5_controller._get_filepath = MagicMock(  # type: ignore
        return_value="Some/Filepath"
    )
    hdf5_controller._client.data = mock_data  # type: ignore
    pipeline_mock = MagicMock()
    mock_create_default_pipeline.side_effect = [pipeline_mock]
    hdf5_controller._num_capture_record = MagicMock()
    hdf5_controller._num_capture_record.get = MagicMock(return_value=5)  # type: ignore

    await hdf5_controller._handle_hdf5_data()

    # Check it ran correctly
    assert hdf5_controller._capture_control_record.get() == 0
    assert (
        hdf5_controller._status_message_record.get()
        == "Requested number of frames captured"
    )
    assert pipeline_mock[0].queue.put_nowait.call_count == 7
    pipeline_mock[0].queue.put_nowait.assert_called_with(EndData(5, EndReason.OK))


@patch("pandablocks_ioc._hdf_ioc.stop_pipeline")
@patch("pandablocks_ioc._hdf_ioc.create_default_pipeline")
async def test_handle_data_two_start_data(
    mock_create_default_pipeline: MagicMock,
    mock_stop_pipeline: MagicMock,
    hdf5_controller: HDF5RecordController,
    slow_dump_expected,
):
    """Test that _handle_hdf5_data works correctly over multiple datasets"""

    async def mock_data(scaled, flush_period):
        doubled_list = list(slow_dump_expected)[:-1]  # cut off EndData
        doubled_list.extend(doubled_list)
        for item in doubled_list:
            yield item

    # Set up all the mocks
    hdf5_controller._get_filepath = MagicMock(  # type: ignore
        return_value="Some/Filepath"
    )
    hdf5_controller._client.data = mock_data  # type: ignore
    pipeline_mock = MagicMock()
    mock_create_default_pipeline.side_effect = [pipeline_mock]
    hdf5_controller._num_capture_record = MagicMock()
    hdf5_controller._num_capture_record.get = MagicMock(return_value=10)  # type: ignore

    await hdf5_controller._handle_hdf5_data()

    # Check it ran correctly
    assert hdf5_controller._capture_control_record.get() == 0
    assert (
        hdf5_controller._status_message_record.get()
        == "Requested number of frames captured"
    )
    # len 13 for 2 StartData, 10 FrameData and 1 EndData
    assert pipeline_mock[0].queue.put_nowait.call_count == 13
    pipeline_mock[0].queue.put_nowait.assert_called_with(EndData(10, EndReason.OK))


@patch("pandablocks_ioc._hdf_ioc.stop_pipeline")
@patch("pandablocks_ioc._hdf_ioc.create_default_pipeline")
async def test_handle_data_mismatching_start_data(
    mock_create_default_pipeline: MagicMock,
    mock_stop_pipeline: MagicMock,
    hdf5_controller: HDF5RecordController,
):
    """Test that _handle_hdf5_data stops capturing when different StartData items
    received"""

    async def mock_data(scaled, flush_period):
        """Return a pair of data captures, with differing StartData items"""
        list = [
            ReadyData(),
            StartData(
                [
                    FieldCapture(
                        name="PCAP.BITS2",
                        type=numpy.dtype("uint32"),
                        capture="Value",
                        scale=1,
                        offset=0,
                        units="",
                    )
                ],
                0,
                "Scaled",
                "Framed",
                52,
                None,
                None,
                None,
            ),
            FrameData(Rows([0, 1, 1, 3, 5.6e-08, 1, 2])),
            # Implicit end of first data here
            ReadyData(),
            StartData([], 0, "Different", "Also Different", 52, None, None, None),
        ]
        for item in list:
            yield item

    # Set up all the mocks
    hdf5_controller._get_filepath = MagicMock(  # type: ignore
        return_value="Some/Filepath"
    )
    hdf5_controller._client.data = mock_data  # type: ignore
    pipeline_mock = MagicMock()
    mock_create_default_pipeline.side_effect = [pipeline_mock]
    hdf5_controller._num_capture_record = MagicMock()
    hdf5_controller._num_capture_record.get = MagicMock(return_value=10)  # type: ignore

    await hdf5_controller._handle_hdf5_data()

    # Check it ran correctly
    assert hdf5_controller._capture_control_record.get() == 0
    assert (
        hdf5_controller._status_message_record.get()
        == "Mismatched StartData packet for file"
    )
    # len 3 - one StartData, one FrameData, one EndData
    assert pipeline_mock[0].queue.put_nowait.call_count == 3
    pipeline_mock[0].queue.put_nowait.assert_called_with(
        EndData(1, EndReason.START_DATA_MISMATCH)
    )


@patch("pandablocks_ioc._hdf_ioc.stop_pipeline")
@patch("pandablocks_ioc._hdf_ioc.create_default_pipeline")
async def test_handle_data_cancelled_error(
    mock_create_default_pipeline: MagicMock,
    mock_stop_pipeline: MagicMock,
    hdf5_controller: HDF5RecordController,
):
    """Test that _handle_hdf5_data stops capturing when it receives a CancelledError"""

    async def mock_data(scaled, flush_period):
        """Return the start of data capture, then raise a CancelledError.
        This mimics the task being cancelled."""
        list = [
            ReadyData(),
            StartData(
                [
                    FieldCapture(
                        name="PCAP.BITS2",
                        type=numpy.dtype("uint32"),
                        capture="Value",
                        scale=1,
                        offset=0,
                        units="",
                    )
                ],
                0,
                "Scaled",
                "Framed",
                52,
                None,
                None,
                None,
            ),
        ]
        for item in list:
            yield item
        raise CancelledError

    # Set up all the mocks
    hdf5_controller._get_filepath = MagicMock(  # type: ignore
        return_value="Some/Filepath"
    )
    hdf5_controller._client.data = mock_data  # type: ignore
    pipeline_mock = MagicMock()
    mock_create_default_pipeline.side_effect = [pipeline_mock]

    await hdf5_controller._handle_hdf5_data()

    # Check it ran correctly
    assert hdf5_controller._capture_control_record.get() == 0
    assert hdf5_controller._status_message_record.get() == "Capturing disabled"
    # len 2 - one StartData, one EndData
    assert pipeline_mock[0].queue.put_nowait.call_count == 2
    pipeline_mock[0].queue.put_nowait.assert_called_with(
        EndData(0, EndReason.MANUALLY_STOPPED)
    )


@patch("pandablocks_ioc._hdf_ioc.stop_pipeline")
@patch("pandablocks_ioc._hdf_ioc.create_default_pipeline")
async def test_handle_data_unexpected_exception(
    mock_create_default_pipeline: MagicMock,
    mock_stop_pipeline: MagicMock,
    hdf5_controller: HDF5RecordController,
):
    """Test that _handle_hdf5_data stops capturing when it receives an unexpected
    exception"""

    async def mock_data(scaled, flush_period):
        """Return the start of data capture, then raise an Exception."""
        list = [
            ReadyData(),
            StartData(
                [
                    FieldCapture(
                        name="PCAP.BITS2",
                        type=numpy.dtype("uint32"),
                        capture="Value",
                        scale=1,
                        offset=0,
                        units="",
                    )
                ],
                0,
                "Scaled",
                "Framed",
                52,
                None,
                None,
                None,
            ),
        ]
        for item in list:
            yield item
        raise Exception("Test exception")

    # Set up all the mocks
    hdf5_controller._get_filepath = MagicMock(  # type: ignore
        return_value="Some/Filepath"
    )
    hdf5_controller._client.data = mock_data  # type: ignore
    pipeline_mock = MagicMock()
    mock_create_default_pipeline.side_effect = [pipeline_mock]

    await hdf5_controller._handle_hdf5_data()

    # Check it ran correctly
    assert hdf5_controller._capture_control_record.get() == 0
    assert (
        hdf5_controller._status_message_record.get()
        == "Capture disabled, unexpected exception"
    )
    # len 2 - one StartData, one EndData
    assert pipeline_mock[0].queue.put_nowait.call_count == 2
    pipeline_mock[0].queue.put_nowait.assert_called_with(
        EndData(0, EndReason.UNKNOWN_EXCEPTION)
    )


async def test_capture_on_update(
    hdf5_controller: HDF5RecordController,
):
    """Test _capture_on_update correctly starts the data capture task"""
    hdf5_controller._handle_hdf5_data = AsyncMock()  # type: ignore

    await hdf5_controller._capture_on_update(1)

    assert hdf5_controller._handle_hdf5_data_task is not None
    hdf5_controller._handle_hdf5_data.assert_called_once()


async def test_capture_on_update_cancel_task(
    hdf5_controller: HDF5RecordController,
):
    """Test _capture_on_update correctly cancels an already running task
    when Capture=0"""

    task_mock = MagicMock()
    hdf5_controller._handle_hdf5_data_task = task_mock

    await hdf5_controller._capture_on_update(0)

    task_mock.cancel.assert_called_once()


async def test_capture_on_update_cancel_unexpected_task(
    hdf5_controller: HDF5RecordController,
):
    """Test _capture_on_update correctly cancels an already running task
    when Capture=1"""
    task_mock = MagicMock()
    hdf5_controller._handle_hdf5_data_task = task_mock
    hdf5_controller._handle_hdf5_data = AsyncMock()  # type: ignore

    await hdf5_controller._capture_on_update(1)

    hdf5_controller._handle_hdf5_data.assert_called_once()  # type: ignore
    task_mock.cancel.assert_called_once()


def test_hdf_get_filepath(
    hdf5_controller: HDF5RecordController,
):
    """Test _get_filepath works when all records have valid values"""

    hdf5_controller._directory_record = MagicMock()
    hdf5_controller._directory_record.get = MagicMock(  # type: ignore
        return_value="/some/path"
    )

    hdf5_controller._file_name_record = MagicMock()
    hdf5_controller._file_name_record.get = MagicMock(  # type: ignore
        return_value="some_filename"
    )

    assert hdf5_controller._get_filepath() == "/some/path/some_filename"


def test_hdf_capture_validate_valid_filename(
    hdf5_controller: HDF5RecordController,
):
    """Test _capture_validate passes when a valid filename is given"""
    hdf5_controller._get_filepath = MagicMock(  # type: ignore
        return_value="/valid/file.h5"
    )

    assert hdf5_controller._capture_validate(None, 1) is True


def test_hdf_capture_validate_new_value_zero(
    hdf5_controller: HDF5RecordController,
):
    """Test _capture_validate passes when new value is zero"""
    assert hdf5_controller._capture_validate(None, 0) is True


def test_hdf_capture_validate_invalid_filename(
    hdf5_controller: HDF5RecordController,
):
    """Test _capture_validate fails when filename cannot be created"""
    hdf5_controller._get_filepath = MagicMock(  # type: ignore
        side_effect=ValueError("Mocked value error")
    )

    assert hdf5_controller._capture_validate(None, 1) is False


def test_hdf_capture_validate_exception(
    hdf5_controller: HDF5RecordController,
):
    """Test _capture_validate fails due to other exceptions"""
    hdf5_controller._get_filepath = MagicMock(  # type: ignore
        side_effect=Exception("Mocked error")
    )

    assert hdf5_controller._capture_validate(None, 1) is False


def test_dataset_name_cache():
    with patch(
        "pandablocks_ioc._hdf_ioc.ReadOnlyPvaTable", autospec=True
    ) as mock_table:
        mock_table_instance = MagicMock()
        mock_table.return_value = mock_table_instance

        # Initialize DatasetNameCache
        datasets = {
            "TEST1:OUT": Dataset("", "Value"),
            "TEST2:OUT": Dataset("test2", "No"),
            "TEST3:OUT": Dataset("test3", "Value"),
            "TEST4:OUT": Dataset("test4", "Min Max Mean"),
            "TEST5:OUT": Dataset("test5", "Min Max"),
        }
        cache = DatasetNameCache(datasets, "record_name")

        # Check that set_rows was called once with the correct arguments
        mock_table_instance.set_rows.assert_called_once_with(
            ["Name", "Type"], [[], []], length=300, default_data_type=str
        )
        cache.update_datasets_record()

        # Check that update_row was called with the correct arguments
        mock_table_instance.update_row.assert_any_call(
            "Name", ["test3", "test4", "test5"]
        )
        mock_table_instance.update_row.assert_any_call(
            "Type", ["float64", "float64", "float64"]
        )

        assert cache.hdf_writer_names() == {
            "TEST3.OUT": {"Value": "test3"},
            "TEST4.OUT": {"Mean": "test4", "Min": "test4-min", "Max": "test4-max"},
            "TEST5.OUT": {"Min": "test5-min", "Max": "test5-max"},
        }
