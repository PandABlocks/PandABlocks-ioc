# Reading and writing the block layout stored by the PandA web GUI's Malcolm server
import asyncio
import json
import logging
from collections.abc import Callable
from typing import Any

from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed, WebSocketException

MALCOLM_PORT = 8008
LAYOUT_PATH = ["PANDA", "layout", "value"]
VISIBLE_LABELS = ["Hidden", "Visible"]

_SUBSCRIBE_ID = 0
_UPDATE_TYPEID = "malcolm:core/Update:1.0"
_ERROR_TYPEID = "malcolm:core/Error:1.0"
_RECONNECT_PERIOD = 5.0

LayoutTable = dict[str, Any]


class MalcolmError(Exception):
    """Raised when the Malcolm server responds with an Error message"""


class MalcolmLayoutClient:
    """Subscribes to, and writes rows of, the `PANDA.layout` table served by the
    Malcolm instance that backs the PandA web GUI.

    The table has list columns `name`, `mri`, `x`, `y` and `visible`, one row per
    block instance (e.g. "PULSE1")."""

    def __init__(self, host: str, port: int = MALCOLM_PORT, timeout: float = 5.0):
        self._url = f"ws://{host}:{port}/ws"
        self._timeout = timeout
        self._ws: ClientConnection | None = None
        self._next_id = _SUBSCRIBE_ID + 1
        self._pending: dict[int, asyncio.Future] = {}
        self._task: asyncio.Task | None = None
        self.table: LayoutTable = {}
        self.on_update: Callable[[LayoutTable], None] | None = None

    async def connect(self) -> LayoutTable:
        """Connect, subscribe to the layout table and return its initial value"""
        ws = await connect(self._url, open_timeout=self._timeout)
        try:
            await ws.send(
                json.dumps(
                    {
                        "typeid": "malcolm:core/Subscribe:1.0",
                        "id": _SUBSCRIBE_ID,
                        "path": LAYOUT_PATH,
                        "delta": False,
                    }
                )
            )
            message = json.loads(await asyncio.wait_for(ws.recv(), self._timeout))
            if message.get("typeid") != _UPDATE_TYPEID:
                raise MalcolmError(f"Unexpected response to layout subscribe: {message}")
        except BaseException:
            await ws.close()
            raise

        self._ws = ws
        self.table = message["value"]
        return self.table

    def start(self) -> None:
        """Start processing subscription updates in the background"""
        self._task = asyncio.create_task(self._run())

    async def close(self) -> None:
        if self._task:
            self._task.cancel()
        if self._ws:
            await self._ws.close()

    async def put(self, name: str, **changes: Any) -> None:
        """Change one or more columns (`x`, `y`, `visible`) of the row for block
        instance `name`, leaving every other row untouched."""
        if self._ws is None:
            raise MalcolmError("Not connected to Malcolm")

        index = self.table["name"].index(name)
        value = {
            column: [values[index]] if isinstance(values, list) else values
            for column, values in self.table.items()
        }
        for column, new_value in changes.items():
            value[column] = [new_value]

        msg_id = self._next_id
        self._next_id += 1
        future = asyncio.get_running_loop().create_future()
        self._pending[msg_id] = future
        try:
            await self._ws.send(
                json.dumps(
                    {
                        "typeid": "malcolm:core/Put:1.0",
                        "id": msg_id,
                        "path": LAYOUT_PATH,
                        "value": value,
                    }
                )
            )
            await asyncio.wait_for(future, self._timeout)
        finally:
            self._pending.pop(msg_id, None)

    def _handle_message(self, message: dict) -> None:
        typeid = message.get("typeid")
        msg_id = message.get("id")
        if msg_id == _SUBSCRIBE_ID:
            if typeid == _UPDATE_TYPEID:
                self.table = message["value"]
                if self.on_update:
                    self.on_update(self.table)
            elif typeid == _ERROR_TYPEID:
                logging.error(f"Malcolm layout subscription error: {message}")
            return

        future = self._pending.get(msg_id)  # type: ignore[arg-type]
        if future is None or future.done():
            return
        if typeid == _ERROR_TYPEID:
            future.set_exception(MalcolmError(message.get("message", str(message))))
        else:
            future.set_result(message.get("value"))

    async def _run(self) -> None:
        while True:
            assert self._ws
            try:
                async for raw in self._ws:
                    try:
                        self._handle_message(json.loads(raw))
                    except Exception:
                        logging.exception("Error handling Malcolm layout message")
            except ConnectionClosed:
                pass

            logging.warning(
                f"Lost connection to Malcolm at {self._url}, layout records will "
                "not update until it is re-established"
            )
            for future in self._pending.values():
                if not future.done():
                    future.set_exception(MalcolmError("Connection to Malcolm lost"))
            self._ws = None

            while self._ws is None:
                await asyncio.sleep(_RECONNECT_PERIOD)
                try:
                    await self.connect()
                except (OSError, TimeoutError, WebSocketException, MalcolmError):
                    continue
                logging.info(f"Reconnected to Malcolm at {self._url}")
                if self.on_update:
                    self.on_update(self.table)
