"""Connection tests for the Tuya local API against a simulated device."""

import asyncio
import json
import struct
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

import pytest

from custom_components.robovac.robovac import RoboVac
from custom_components.robovac.tuyalocalapi import TuyaCipher, crc

LOCAL_KEY = "0123456789abcdef"
MAGIC_SUFFIX = struct.pack(">I", 0x0000AA55)


class FakeVacuum:
    """Minimal Tuya 3.3 device: answers queries, heartbeats and commands."""

    def __init__(self) -> None:
        self.dps = {"2": False, "5": "Auto", "15": "Charging", "104": 90}
        self.commands: list[dict] = []
        self.connections = 0
        self.close_after: float | None = None
        self.timers: list[asyncio.TimerHandle] = []
        self.server: asyncio.Server | None = None

    @property
    def port(self) -> int:
        assert self.server is not None
        return self.server.sockets[0].getsockname()[1]

    @staticmethod
    def _frame(seq: int, cmd: int, payload: bytes) -> bytes:
        body = struct.pack(">I", 0) + payload
        header = struct.pack(">IIII", 0x000055AA, seq, cmd, len(body) + 8)
        return header + body + struct.pack(">II", crc(header + body), 0x0000AA55)

    async def handle(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        self.connections += 1
        cipher = TuyaCipher(LOCAL_KEY, (3, 3))
        if self.close_after is not None:
            self.timers.append(
                asyncio.get_running_loop().call_later(self.close_after, writer.close)
            )
        try:
            while True:
                data = await reader.readuntil(MAGIC_SUFFIX)
                _, seq, cmd, size = struct.unpack_from(">IIII", data)
                payload = data[16:16 + size - 8]
                if cmd == 0x09:
                    writer.write(self._frame(seq, 0x09, b""))
                elif cmd == 0x0A:
                    out = cipher.encrypt(0x0A, json.dumps({"dps": self.dps}).encode())
                    writer.write(self._frame(seq, 0x0A, out))
                elif cmd == 0x07:
                    dps = json.loads(cipher.decrypt(cmd, payload))["dps"]
                    self.commands.append(dps)
                    self.dps.update(dps)
                    writer.write(self._frame(seq, 0x07, b""))
                    out = cipher.encrypt(0x08, json.dumps({"dps": dps}).encode())
                    writer.write(self._frame(0, 0x08, out))
                await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError):
            pass


@pytest.fixture
async def fake_vacuum(socket_enabled) -> AsyncIterator[FakeVacuum]:
    device = FakeVacuum()
    device.server = await asyncio.start_server(device.handle, "127.0.0.1", 0)
    yield device
    for timer in device.timers:
        timer.cancel()
    device.server.close()
    await device.server.wait_closed()


@pytest.fixture
async def robovac(fake_vacuum: FakeVacuum) -> AsyncIterator[RoboVac]:
    vac = RoboVac(
        model_code="T2259",
        device_id="test_device",
        host="127.0.0.1",
        port=fake_vacuum.port,
        local_key=LOCAL_KEY,
        timeout=2,
        ping_interval=10,
        update_entity_state=AsyncMock(),
    )
    yield vac
    await vac.async_disable()
    for task in asyncio.all_tasks():
        if task is not asyncio.current_task():
            task.cancel()


async def _wait_for(condition, timeout: float = 3) -> None:
    async with asyncio.timeout(timeout):
        while not condition():
            await asyncio.sleep(0.05)


async def test_first_poll_returns_state(robovac: RoboVac) -> None:
    """A poll made before the connection is open still gets the reply."""
    assert not robovac._connected
    await robovac.async_get()
    assert robovac._dps["15"] == "Charging"


async def test_commands_delivered(robovac: RoboVac, fake_vacuum: FakeVacuum) -> None:
    """Every command reaches the device and its pushed update is applied."""
    for dps in ({"5": "Auto"}, {"2": False}, {"101": True}):
        await robovac.async_set(dps)
    await _wait_for(lambda: len(fake_vacuum.commands) == 3)
    assert fake_vacuum.commands == [{"5": "Auto"}, {"2": False}, {"101": True}]
    await _wait_for(lambda: robovac._dps.get("101") is True)


async def test_commands_survive_device_closing_connection(
    robovac: RoboVac, fake_vacuum: FakeVacuum
) -> None:
    """When the device closes the connection, the next command reconnects."""
    fake_vacuum.close_after = 0.3
    await robovac.async_get()

    await _wait_for(lambda: not robovac._connected)
    await robovac.async_set({"5": "Auto"})
    await _wait_for(lambda: fake_vacuum.commands == [{"5": "Auto"}])

    await _wait_for(lambda: not robovac._connected)
    await robovac.async_set({"2": False})
    await _wait_for(lambda: fake_vacuum.commands == [{"5": "Auto"}, {"2": False}])
    assert fake_vacuum.connections == 3
