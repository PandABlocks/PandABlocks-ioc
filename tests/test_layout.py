import asyncio
import json

import pytest
from pandablocks.asyncio import AsyncioClient
from websockets.asyncio.server import ServerConnection, serve

from fixtures.mocked_panda import TEST_PREFIX
from pandablocks_ioc._layout import LAYOUT_PATH, MalcolmError, MalcolmLayoutClient
from pandablocks_ioc._pvi import Pvi, PviGroup
from pandablocks_ioc.ioc import IocRecordFactory


class FakeMalcolm:
    """Minimal Malcolm websocket server serving a PANDA.layout table"""

    def __init__(self):
        self.table = {
            "typeid": "malcolm:core/Table:1.0",
            "name": ["PULSE1", "PCAP"],
            "mri": ["PANDA:PULSE1", "PANDA:PCAP"],
            "x": [10.0, 20.0],
            "y": [30.0, 40.0],
            "visible": [True, False],
        }
        self.puts: list[dict] = []
        self.reject_puts = False
        self.subscribers: list[tuple[ServerConnection, int]] = []

    async def publish(self):
        for ws, msg_id in self.subscribers:
            await ws.send(
                json.dumps(
                    {
                        "typeid": "malcolm:core/Update:1.0",
                        "id": msg_id,
                        "value": self.table,
                    }
                )
            )

    async def handler(self, ws: ServerConnection):
        async for raw in ws:
            message = json.loads(raw)
            assert message["path"] == LAYOUT_PATH
            if message["typeid"] == "malcolm:core/Subscribe:1.0":
                self.subscribers.append((ws, message["id"]))
                await self.publish()
            elif message["typeid"] == "malcolm:core/Put:1.0":
                self.puts.append(message["value"])
                if self.reject_puts:
                    await ws.send(
                        json.dumps(
                            {
                                "typeid": "malcolm:core/Error:1.0",
                                "id": message["id"],
                                "message": "Rejected",
                            }
                        )
                    )
                    continue
                value = message["value"]
                for row, name in enumerate(value["name"]):
                    index = self.table["name"].index(name)
                    for column in ("x", "y", "visible"):
                        self.table[column][index] = value[column][row]
                await ws.send(
                    json.dumps(
                        {
                            "typeid": "malcolm:core/Return:1.0",
                            "id": message["id"],
                            "value": None,
                        }
                    )
                )
                await self.publish()


@pytest.fixture
async def fake_malcolm():
    malcolm = FakeMalcolm()
    async with serve(malcolm.handler, "localhost", 0) as server:
        port = next(iter(server.sockets)).getsockname()[1]
        yield malcolm, port


async def test_layout_client_connect_and_put(fake_malcolm):
    malcolm, port = fake_malcolm
    client = MalcolmLayoutClient("localhost", port)
    table = await client.connect()
    assert table["name"] == ["PULSE1", "PCAP"]

    updates = asyncio.Queue()
    client.on_update = updates.put_nowait
    client.start()
    try:
        await client.put("PCAP", x=99.0, visible=True)
        # Only the changed row is sent, with untouched columns from the cache
        assert malcolm.puts == [
            {
                "typeid": "malcolm:core/Table:1.0",
                "name": ["PCAP"],
                "mri": ["PANDA:PCAP"],
                "x": [99.0],
                "y": [40.0],
                "visible": [True],
            }
        ]
        update = await asyncio.wait_for(updates.get(), 1)
        assert update["x"] == [10.0, 99.0]
        assert update["visible"] == [True, True]

        malcolm.reject_puts = True
        with pytest.raises(MalcolmError, match="Rejected"):
            await client.put("PULSE1", y=1.0)
    finally:
        await client.close()


async def test_layout_records(fake_malcolm, clear_records):
    malcolm, port = fake_malcolm
    client = MalcolmLayoutClient("localhost", port)
    await client.connect()
    factory = IocRecordFactory(AsyncioClient("123"), TEST_PREFIX, {})

    records = factory.create_layout_records("PULSE1", "PULSE1", client)
    assert set(records) == {
        "PULSE1:LAYOUT:X",
        "PULSE1:LAYOUT:Y",
        "PULSE1:LAYOUT:VISIBLE",
    }
    assert records["PULSE1:LAYOUT:X"].record.get() == 10.0
    assert records["PULSE1:LAYOUT:Y"].record.get() == 30.0
    assert records["PULSE1:LAYOUT:VISIBLE"].record.get() == 1
    assert PviGroup.LAYOUT in Pvi.pvi_info_dict["PULSE1"]

    table = dict(client.table, x=[55.0, 20.0], visible=[False, False])
    factory.update_layout_records(table)
    assert records["PULSE1:LAYOUT:X"].record.get() == 55.0
    assert records["PULSE1:LAYOUT:VISIBLE"].record.get() == 0

    await client.close()
