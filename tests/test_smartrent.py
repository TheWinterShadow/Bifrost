"""Tests for SmartRent client wrapper."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bifrost.utils.smartrent import DeviceInventory, SmartRentClient

# ── DeviceInventory ──────────────────────────────────────────────────────────


def test_empty_inventory() -> None:
    inv = DeviceInventory()
    assert inv.count == 0
    assert inv.all_devices == []


def test_inventory_count() -> None:
    inv = DeviceInventory(
        locks=[MagicMock()],
        thermostats=[MagicMock(), MagicMock()],
    )
    assert inv.count == 3


def test_inventory_all_devices_flat() -> None:
    lock = MagicMock()
    thermo = MagicMock()
    switch = MagicMock()
    inv = DeviceInventory(locks=[lock], thermostats=[thermo], binary_switches=[switch])
    assert inv.all_devices == [lock, thermo, switch]


# ── SmartRentClient ──────────────────────────────────────────────────────────


@pytest.fixture
def client() -> SmartRentClient:
    return SmartRentClient("test@example.com", "hunter2")


def test_not_connected_by_default(client: SmartRentClient) -> None:
    assert not client.is_connected


def test_inventory_raises_before_connect(client: SmartRentClient) -> None:
    with pytest.raises(RuntimeError, match="Not connected"):
        _ = client.inventory


@pytest.mark.asyncio
@patch("bifrost.utils.smartrent.async_login", new_callable=AsyncMock)
async def test_connect(mock_login: AsyncMock, client: SmartRentClient) -> None:
    api = MagicMock()
    api.get_locks.return_value = [MagicMock()]
    api.get_thermostats.return_value = []
    api.get_binary_switches.return_value = []
    api.get_multilevel_switches.return_value = [MagicMock(), MagicMock()]
    api.get_leak_sensors.return_value = []
    api.get_motion_sensors.return_value = []
    mock_login.return_value = api

    inv = await client.connect()

    mock_login.assert_awaited_once_with("test@example.com", "hunter2")
    assert client.is_connected
    assert inv.count == 3
    assert len(inv.locks) == 1
    assert len(inv.multilevel_switches) == 2


@pytest.mark.asyncio
@patch("bifrost.utils.smartrent.async_login", new_callable=AsyncMock)
async def test_getter_methods(mock_login: AsyncMock, client: SmartRentClient) -> None:
    lock = MagicMock()
    thermo = MagicMock()
    bswitch = MagicMock()
    mswitch = MagicMock()
    leak = MagicMock()
    motion = MagicMock()
    api = MagicMock()
    api.get_locks.return_value = [lock]
    api.get_thermostats.return_value = [thermo]
    api.get_binary_switches.return_value = [bswitch]
    api.get_multilevel_switches.return_value = [mswitch]
    api.get_leak_sensors.return_value = [leak]
    api.get_motion_sensors.return_value = [motion]
    mock_login.return_value = api

    await client.connect()

    assert client.get_thermostats() == [thermo]
    assert client.get_locks() == [lock]
    assert client.get_binary_switches() == [bswitch]
    assert client.get_multilevel_switches() == [mswitch]
    assert client.get_leak_sensors() == [leak]
    assert client.get_motion_sensors() == [motion]


def test_getters_raise_before_connect(client: SmartRentClient) -> None:
    with pytest.raises(RuntimeError, match="Not connected"):
        client.get_thermostats()


@pytest.mark.asyncio
@patch("bifrost.utils.smartrent.async_login", new_callable=AsyncMock)
async def test_start_updaters(mock_login: AsyncMock, client: SmartRentClient) -> None:
    device1 = MagicMock()
    device2 = MagicMock()
    api = MagicMock()
    api.get_locks.return_value = [device1]
    api.get_thermostats.return_value = [device2]
    api.get_binary_switches.return_value = []
    api.get_multilevel_switches.return_value = []
    api.get_leak_sensors.return_value = []
    api.get_motion_sensors.return_value = []
    mock_login.return_value = api

    await client.connect()
    client.start_updaters()

    device1.start_updater.assert_called_once()
    device2.start_updater.assert_called_once()


@pytest.mark.asyncio
@patch("bifrost.utils.smartrent.async_login", new_callable=AsyncMock)
async def test_start_updaters_idempotent(mock_login: AsyncMock, client: SmartRentClient) -> None:
    device = MagicMock()
    api = MagicMock()
    api.get_locks.return_value = [device]
    api.get_thermostats.return_value = []
    api.get_binary_switches.return_value = []
    api.get_multilevel_switches.return_value = []
    api.get_leak_sensors.return_value = []
    api.get_motion_sensors.return_value = []
    mock_login.return_value = api

    await client.connect()
    client.start_updaters()
    client.start_updaters()

    device.start_updater.assert_called_once()


@pytest.mark.asyncio
@patch("bifrost.utils.smartrent.async_login", new_callable=AsyncMock)
async def test_stop_updaters(mock_login: AsyncMock, client: SmartRentClient) -> None:
    device = MagicMock()
    api = MagicMock()
    api.get_locks.return_value = [device]
    api.get_thermostats.return_value = []
    api.get_binary_switches.return_value = []
    api.get_multilevel_switches.return_value = []
    api.get_leak_sensors.return_value = []
    api.get_motion_sensors.return_value = []
    mock_login.return_value = api

    await client.connect()
    client.start_updaters()
    client.stop_updaters()

    device.stop_updater.assert_called_once()


@pytest.mark.asyncio
@patch("bifrost.utils.smartrent.async_login", new_callable=AsyncMock)
async def test_stop_updaters_noop_when_not_running(
    mock_login: AsyncMock, client: SmartRentClient
) -> None:
    device = MagicMock()
    api = MagicMock()
    api.get_locks.return_value = [device]
    api.get_thermostats.return_value = []
    api.get_binary_switches.return_value = []
    api.get_multilevel_switches.return_value = []
    api.get_leak_sensors.return_value = []
    api.get_motion_sensors.return_value = []
    mock_login.return_value = api

    await client.connect()
    client.stop_updaters()

    device.stop_updater.assert_not_called()


@pytest.mark.asyncio
@patch("bifrost.utils.smartrent.async_login", new_callable=AsyncMock)
async def test_set_update_callback(mock_login: AsyncMock, client: SmartRentClient) -> None:
    device1 = MagicMock()
    device2 = MagicMock()
    api = MagicMock()
    api.get_locks.return_value = [device1]
    api.get_thermostats.return_value = [device2]
    api.get_binary_switches.return_value = []
    api.get_multilevel_switches.return_value = []
    api.get_leak_sensors.return_value = []
    api.get_motion_sensors.return_value = []
    mock_login.return_value = api

    await client.connect()
    cb = MagicMock()
    client.set_update_callback(cb)

    device1.set_update_callback.assert_called_once_with(cb)
    device2.set_update_callback.assert_called_once_with(cb)


@pytest.mark.asyncio
@patch("bifrost.utils.smartrent.async_login", new_callable=AsyncMock)
async def test_disconnect(mock_login: AsyncMock, client: SmartRentClient) -> None:
    api = MagicMock()
    api.get_locks.return_value = []
    api.get_thermostats.return_value = []
    api.get_binary_switches.return_value = []
    api.get_multilevel_switches.return_value = []
    api.get_leak_sensors.return_value = []
    api.get_motion_sensors.return_value = []
    mock_login.return_value = api

    await client.connect()
    assert client.is_connected

    await client.disconnect()
    assert not client.is_connected

    with pytest.raises(RuntimeError, match="Not connected"):
        _ = client.inventory
