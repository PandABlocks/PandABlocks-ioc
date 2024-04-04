import asyncio
import logging
import sys
from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
from io import BufferedReader
from itertools import chain, repeat
from logging import handlers
from multiprocessing import Queue, get_context
from multiprocessing.connection import Connection
from pathlib import Path
from typing import Any, Generator, Iterator, Optional, Tuple, TypeVar
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from aioca import purge_channel_caches
from pandablocks.commands import (
    Arm,
    ChangeGroup,
    Command,
    Disarm,
    GetBlockInfo,
    GetChanges,
    GetFieldInfo,
    GetLine,
    Put,
)
from pandablocks.connections import DataConnection
from pandablocks.responses import (
    BitMuxFieldInfo,
    BlockInfo,
    Changes,
    EnumFieldInfo,
    TimeFieldInfo,
)
from softioc import builder

from pandablocks_ioc import create_softioc
from pandablocks_ioc._types import EpicsName
from pandablocks_ioc.ioc import _TimeRecordUpdater

T = TypeVar("T")


# If the test is cancelled half way through then the softioc process isn't always killed
# Use the unique TEST_PREFIX to ensure this isn't a problem for future tests
BOBFILE_DIR = Path(__file__).parent.parent / "test-bobfiles"
TIMEOUT = 10
TEST_PREFIX = "TEST_PREFIX"


def append_random_uppercase(pv: str) -> str:
    return pv + "-" + str(uuid4())[:8].upper()


@pytest.fixture
def new_random_test_prefix():
    return append_random_uppercase(TEST_PREFIX)


def multiprocessing_queue_to_list(queue: Queue):
    queue.put(None)
    return list(iter(queue.get, None))


@pytest_asyncio.fixture
def mocked_time_record_updater(
    new_random_test_prefix,
) -> Generator[Tuple[_TimeRecordUpdater, str], None, None]:
    """An instance of _TimeRecordUpdater with MagicMocks and some default values"""
    base_record = MagicMock()
    base_record.name = new_random_test_prefix + ":BASE:RECORD"

    # We don't have AsyncMock in Python3.7, so do it ourselves
    client = MagicMock()
    loop = asyncio.BaseEventLoop()
    try:
        f: asyncio.Future = asyncio.Future(loop=loop)
        f.set_result("8e-09")
        client.send.return_value = f

        mocked_record_info = MagicMock()
        mocked_record_info.record = MagicMock()
        mocked_record_info.record.name = EpicsName(new_random_test_prefix + ":TEST:STR")

        yield (
            _TimeRecordUpdater(
                mocked_record_info,
                new_random_test_prefix,
                client,
                {},
                ["TEST1", "TEST2", "TEST3"],
                base_record,
                True,
            ),
            new_random_test_prefix,
        )
    finally:
        loop.close()


@pytest.fixture
def clear_records():
    # Remove any records created at epicsdbbuilder layer
    builder.ClearRecords()


def custom_logger():
    """Add a custom logger that prints everything to subprocess's stderr,
    otherwise pytest doesn't see logging messages from spawned Processes"""
    sh = logging.StreamHandler(sys.stderr)
    sh.setLevel(logging.WARNING)
    logging.getLogger("").addHandler(sh)


@pytest.fixture(autouse=True)
def aioca_cleanup():
    """Purge the aioca channel cache as the test terminates.
    This suppresses spurious "IOC disconnected" error messages"""
    yield
    purge_channel_caches()


def command_to_key(dataclass_object: Command):
    """Creates a tuple for a given `Command` dataclass so that we can use commands
    as keys in the response dictionary"""

    # The object should be a dataclass_object and and instance
    if is_dataclass(dataclass_object) and not isinstance(dataclass_object, type):
        parsed_dataclass_object = asdict(dataclass_object)
        for key, value in parsed_dataclass_object.items():
            if isinstance(value, list):
                parsed_dataclass_object[key] = tuple(value)

        return (
            dataclass_object.__class__,
            *(
                (
                    key,
                    value,
                )  # if not isinstance(key, dict) else (frozenset(key), value)
                for key, value in sorted(parsed_dataclass_object.items())
                if key != "_commands_map"
            ),
        )

    return dataclass_object


class ResponseHandler:
    def __init__(self, responses):
        if responses:
            self.responses = responses

    def __call__(self, command: Command[T]) -> Any:
        key = command_to_key(command)

        if key not in self.responses:
            raise RuntimeError(
                f"Error in mocked panda, command {command} was passed in, "
                f"the mocked responses defined for are: {[self.responses.keys()]}"
            )

        try:
            response = next(self.responses[key])
        except StopIteration as err:  # Only happens if the client has disconnected
            raise asyncio.TimeoutError from err

        return response

        return next(self.responses[key])


class Rows:
    def __init__(self, *rows):
        self.rows = rows

    def __len__(self):
        return len(self.rows)

    def __eq__(self, o):
        same = o.tolist() == [pytest.approx(row) for row in self.rows]
        return same


class MockedAsyncioClient:
    def __init__(
        self,
        response_handler: ResponseHandler,
        child_conn: Optional[Connection] = None,
        command_queue: Optional[Queue] = None,
    ) -> None:
        self.response_handler = response_handler
        self.command_queue = command_queue
        self.child_conn = child_conn
        self.introspect_panda_ran_already = False

    async def connect(self):
        """Connect does nothing"""
        pass

    async def send(self, command: Command[T], *args: float) -> T:
        """Returns the response, args may include timeout"""
        if self.command_queue:
            self.command_queue.put(command_to_key(command))

        if (
            not self.introspect_panda_ran_already
            and self.child_conn
            and isinstance(command, GetChanges)
        ):
            self.introspect_panda_ran_already = True

            # Now the panda has set up, tell the test to start
            self.child_conn.send("R")

        return self.response_handler(command)

    def is_connected(self):
        return False

    async def close(self):
        pass

    async def data(
        self,
        scaled: bool = True,
        flush_period: Optional[float] = None,
        frame_timeout: Optional[float] = None,
    ):
        flush_every_frame = flush_period is None
        conn = DataConnection()
        conn.connect(scaled)
        with open(Path(__file__).parent.parent / "raw_dump.txt", "rb") as f:
            for raw in chunked_read(f, 200000):
                for data in conn.receive_bytes(
                    raw, flush_every_frame=flush_every_frame
                ):
                    yield data


def get_multiprocessing_context():
    """Tests must use "forkserver" method. If we use "fork" we inherit some
    state from Channel Access from test-to-test, which causes test hangs.
    We cannot use multiprocessing.set_start_method() as it doesn't work inside
    of Pytest."""
    if sys.platform == "win32":
        start_method = "spawn"
    else:
        start_method = "forkserver"
    return get_context(start_method)


def enable_codecov_multiprocess():
    """Code to enable pytest-cov to work properly with multiprocessing"""
    try:
        from pytest_cov.embed import cleanup_on_sigterm
    except ImportError:
        pass
    else:
        cleanup_on_sigterm()


def select_and_recv(conn: Connection):
    """Wait for the given Connection to have data to receive, and return it.
    If a character is provided check its correct before returning it."""
    rrdy = False
    if conn.poll(TIMEOUT):
        rrdy = True

    if rrdy:
        val = conn.recv()
    else:
        pytest.fail("Did not receive anything before timeout")

    return val


@patch("pandablocks_ioc.ioc.softioc.interactive_ioc")
def ioc_wrapper(
    response_handler: ResponseHandler,
    bobfile_dir: Path,
    child_conn: Connection,
    command_queue: Queue,
    table_field_info,
    table_fields,
    test_prefix: str,
    clear_bobfiles,
    mocked_interactive_ioc: MagicMock,
):
    enable_codecov_multiprocess()

    async def inner_wrapper():
        create_softioc(
            MockedAsyncioClient(
                response_handler, child_conn=child_conn, command_queue=command_queue
            ),
            test_prefix,
            screens_dir=bobfile_dir,
            clear_bobfiles=clear_bobfiles,
        )

        # Leave this process running until its torn down by pytest
        await asyncio.Event().wait()

    asyncio.run(inner_wrapper())


@pytest.fixture
def caplog_workaround():
    """Create a logger handler to capture all log messages done in child process,
    then print them to the main thread's stdout/stderr so pytest's caplog fixture
    can see them
    See https://stackoverflow.com/questions/63052171/empty-messages-in-caplog-when-logs-emmited-in-a-different-process/63054881#63054881
    """  # noqa: E501

    @contextmanager
    def ctx() -> Generator[None, None, None]:
        ctx = get_multiprocessing_context()
        logger_queue = ctx.Queue()
        logger = logging.getLogger()
        logger.addHandler(handlers.QueueHandler(logger_queue))
        yield
        while not logger_queue.empty():
            log_record: logging.LogRecord = logger_queue.get()
            # Make mypy happy
            assert (
                log_record.args
            ), f"args were none, how did that happen?\nRecord: {log_record}\n"
            f"Args: {log_record.args}"
            logger._log(
                level=log_record.levelno,
                msg=log_record.message,
                args=log_record.args,
                exc_info=log_record.exc_info,
            )

    return ctx


def create_subprocess_ioc_and_responses(
    response_handler: ResponseHandler,
    tmp_path: Path,
    test_prefix: str,
    caplog,
    caplog_workaround,
    table_field_info,
    table_fields,
    clear_bobfiles=False,
) -> Generator[Tuple[Path, Connection, ResponseHandler, Queue, str], None, None]:
    """Run the IOC in its own subprocess. When finished check logging logged no
    messages of WARNING or higher level."""

    with caplog.at_level(logging.WARNING):
        with caplog_workaround():
            ctx = get_multiprocessing_context()
            command_queue: Queue = ctx.Queue()
            parent_conn, child_conn = ctx.Pipe()
            p = ctx.Process(
                target=ioc_wrapper,
                args=(
                    response_handler,
                    tmp_path,
                    child_conn,
                    command_queue,
                    table_fields,
                    table_field_info,
                    test_prefix,
                    clear_bobfiles,
                ),
            )
            try:
                p.start()
                select_and_recv(parent_conn)  # Wait for IOC to start up
                yield tmp_path, child_conn, response_handler, command_queue, test_prefix
            finally:
                command_queue.close()
                child_conn.close()
                parent_conn.close()
                p.terminate()
                p.join(timeout=TIMEOUT)

                # Should never take anywhere near 10 seconds to terminate, it's just
                # there to ensure the test doesn't hang indefinitely during cleanup

    # We expect all tests to pass without warnings (or worse) logged.
    assert (
        len(caplog.messages) == 0
    ), f"At least one warning/error/exception logged during test: {caplog.records}"


def changes_iterator_wrapper(values=None, multiline_values=None):
    multiline_values = multiline_values or {}
    return [
        Changes(
            values=values, no_value=[], in_error=[], multiline_values=multiline_values
        ),
    ]


def respond_with_no_changes(number_of_iterations: int = 0) -> repeat:
    changes = Changes(
        values={},
        no_value=[],
        in_error=[],
        multiline_values={},
    )

    if number_of_iterations:
        # Unfortunately number_of_iterations being `0` or `None` doesn't cause
        # `repeat(changes)`
        return repeat(changes, number_of_iterations)
    return repeat(changes)


@pytest.fixture
def multiple_seq_responses(table_field_info, table_data_1, table_data_2):
    """
    Used by MockedAsyncioClient to generate panda responses to the ioc's commands.
    Keys are the commands recieved from the ioc (wrapped in a function to make them
    immutable). Values are generators for the responses the dummy panda gives: the
    client.send() calls next on them.

    GetChanges is polled at 10Hz if a different command isn't made.
    """
    return {
        command_to_key(
            Put(
                field="SEQ1.TABLE",
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
        ): repeat(None),
        command_to_key(
            Put(
                field="SEQ2.TABLE",
                value=[
                    "2457862145",
                    "4294967291",
                    "100",
                    "0",
                    "269877249",
                    "678",
                    "0",
                    "55",
                    "4293918721",
                    "0",
                    "9",
                    "9999",
                ],
            )
        ): repeat(None),
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
        ): repeat(None),
        command_to_key(
            Put(
                field="SEQ3.TABLE",
                value=[
                    "2457862144",
                    "4294967291",
                    "100",
                    "0",
                    "269877249",
                    "678",
                    "0",
                    "55",
                    "4293918720",
                    "0",
                    "9",
                    "9999",
                ],
            )
        ): repeat(None),
        # DRVL changing from 8e-06 ms to minutes
        command_to_key(GetFieldInfo(block="SEQ", extended_metadata=True)): repeat(
            {"TABLE": table_field_info}
        ),
        command_to_key(GetBlockInfo(skip_description=False)): repeat(
            {
                "SEQ": BlockInfo(number=4, description="SEQ Desc"),
            }
        ),
        command_to_key(
            Put(field="*METADATA.LABEL_SEQ1", value="SomeOtherSequenceMetadataLabel")
        ): repeat("OK"),
        command_to_key(Put(field="SEQ2.LABEL")): repeat(None),
        # Changes are given at 10Hz, the changes provided are used for many
        # different tests
        command_to_key(GetChanges(group=ChangeGroup.ALL, get_multiline=True)): chain(
            # Initial value of every field
            changes_iterator_wrapper(
                values={
                    "*METADATA.LABEL_SEQ1": "SeqMetadataLabel",
                    "*METADATA.LABEL_SEQ2": "SeqMetadataLabel",
                    "*METADATA.LABEL_SEQ3": "SeqMetadataLabel",
                    "*METADATA.LABEL_SEQ4": "SeqMetadataLabel",
                },
                multiline_values={
                    "SEQ1.TABLE": table_data_1,
                    "SEQ2.TABLE": table_data_2,
                    "SEQ3.TABLE": [],
                    "SEQ4.TABLE": [],
                },
            ),
            respond_with_no_changes(number_of_iterations=50),
            changes_iterator_wrapper(
                values={},
                multiline_values={
                    "SEQ3.TABLE": table_data_1,
                },
            ),
            # Keep the panda active with no changes until pytest tears it down
            respond_with_no_changes(),
        ),
    }


@pytest.fixture
def no_numbered_suffix_to_metadata_responses(table_field_info, table_data_1):
    """
    Used to test if pandablocks will fail if the *METADATA.LABEL_X
    doesn't have a suffixed number.
    """
    return {
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
        ): repeat(None),
        # DRVL changing from 8e-06 ms to minutes
        command_to_key(GetFieldInfo(block="SEQ", extended_metadata=True)): repeat(
            {"TABLE": table_field_info}
        ),
        command_to_key(GetBlockInfo(skip_description=False)): repeat(
            {
                "SEQ": BlockInfo(number=1, description="SEQ Desc"),
            }
        ),
        # Changes are given at 10Hz, the changes provided are used for many
        # different tests
        command_to_key(GetChanges(group=ChangeGroup.ALL, get_multiline=True)): chain(
            # Initial value of every field
            changes_iterator_wrapper(
                values={
                    "*METADATA.LABEL_SEQ": "SeqMetadataLabel",
                },
                multiline_values={
                    "SEQ.TABLE": table_data_1,
                },
            ),
            # Keep the panda active with no changes until pytest tears it down
            respond_with_no_changes(),
        ),
    }


@pytest.fixture
def faulty_multiple_pcap_responses():
    """
    Used to test if the ioc will fail with an error if the user abuses
    the new numbering system.
    """
    pcap_info = {
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
    return {
        command_to_key(GetFieldInfo(block="PCAP1", extended_metadata=True)): repeat(
            pcap_info
        ),
        command_to_key(GetFieldInfo(block="PCAP2", extended_metadata=True)): repeat(
            pcap_info
        ),
        command_to_key(GetBlockInfo(skip_description=False)): repeat(
            {
                "PCAP1": BlockInfo(number=1, description="PCAP Desc"),
                "PCAP": BlockInfo(number=2, description="PCAP Desc"),
            }
        ),
        # Changes are given at 10Hz, the changes provided are used for many
        # different tests
        command_to_key(GetChanges(group=ChangeGroup.ALL, get_multiline=True)): chain(
            # Initial value of every field
            changes_iterator_wrapper(
                values={
                    "PCAP1.TRIG_EDGE": "Falling",
                    "PCAP1.GATE": "CLOCK1.OUT",
                    "PCAP1.GATE.DELAY": "1",
                    "PCAP1.ARM": "0",
                    "*METADATA.LABEL_PCAP1": "PcapMetadataLabel",
                    "PCAP2.TRIG_EDGE": "Falling",
                    "PCAP2.GATE": "CLOCK1.OUT",
                    "PCAP2.GATE.DELAY": "1",
                    "PCAP2.ARM": "0",
                    "*METADATA.LABEL_PCAP2": "PcapMetadataLabel",
                },
            ),
            # Keep the panda active with no changes until pytest tears it down
            respond_with_no_changes(),
        ),
    }


@pytest.fixture
def standard_responses_no_panda_update(table_field_info, table_data_1):
    """
    Used to test if the softioc can be started.
    """
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
        command_to_key(GetFieldInfo(block="SEQ", extended_metadata=True)): repeat(
            {"TABLE": table_field_info}
        ),
        command_to_key(GetBlockInfo(skip_description=False)): repeat(
            {
                "PCAP": BlockInfo(number=1, description="PCAP Desc"),
                "SEQ": BlockInfo(number=1, description="SEQ Desc"),
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
                },
                multiline_values={"SEQ.TABLE": table_data_1},
            ),
            respond_with_no_changes(),
        ),
    }


@pytest.fixture
def standard_responses(table_field_info, table_data_1, table_data_2):
    """
    Used by MockedAsyncioClient to generate panda responses to the ioc's commands.
    Keys are the commands recieved from the ioc (wrapped in a function to make them
    immutable). Values are generators for the responses the dummy panda gives: the
    client.send() calls next on them.

    GetChanges is polled at 10Hz if a different command isn't made.
    """
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
        ): repeat(None),
        command_to_key(
            Put(
                field="SEQ.TABLE",
                value=[
                    "2457862145",
                    "4294967291",
                    "100",
                    "0",
                    "269877249",
                    "678",
                    "0",
                    "55",
                    "4293918721",
                    "0",
                    "9",
                    "9999",
                ],
            )
        ): repeat(None),
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
            # Keep the panda active with no changes until pytest tears it down
            respond_with_no_changes(),
        ),
    }


@pytest.fixture
def mocked_panda_multiple_seq_responses(
    multiple_seq_responses,
    new_random_test_prefix,
    tmp_path: Path,
    caplog,
    caplog_workaround,
    table_field_info,
    table_fields,
    clear_records,
) -> Generator[Tuple[Path, Connection, ResponseHandler, Queue, str], None, None]:
    response_handler = ResponseHandler(multiple_seq_responses)

    yield from create_subprocess_ioc_and_responses(
        response_handler,
        tmp_path,
        new_random_test_prefix,
        caplog,
        caplog_workaround,
        table_field_info,
        table_fields,
    )


@pytest.fixture
def mocked_panda_standard_responses(
    standard_responses,
    new_random_test_prefix,
    tmp_path: Path,
    caplog,
    caplog_workaround,
    table_field_info,
    table_fields,
    clear_records,
) -> Generator[Tuple[Path, Connection, ResponseHandler, Queue, str], None, None]:
    response_handler = ResponseHandler(standard_responses)

    yield from create_subprocess_ioc_and_responses(
        response_handler,
        tmp_path,
        new_random_test_prefix,
        caplog,
        caplog_workaround,
        table_field_info,
        table_fields,
    )


@pytest.fixture
def mocked_panda_standard_responses_no_panda_update(
    standard_responses_no_panda_update,
    new_random_test_prefix,
    tmp_path: Path,
    caplog,
    caplog_workaround,
    table_field_info,
    table_fields,
    clear_records,
) -> Generator[Tuple[Path, Connection, ResponseHandler, Queue, str], None, None]:
    response_handler = ResponseHandler(standard_responses_no_panda_update)

    yield from create_subprocess_ioc_and_responses(
        response_handler,
        tmp_path,
        new_random_test_prefix,
        caplog,
        caplog_workaround,
        table_field_info,
        table_fields,
    )


def chunked_read(f: BufferedReader, size: int) -> Iterator[bytes]:
    data = f.read(size)
    while data:
        yield data
        data = f.read(size)
