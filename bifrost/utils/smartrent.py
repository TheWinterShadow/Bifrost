"""SmartRent API client wrapper.

Wraps smartrent-py to provide a typed, lifecycle-managed interface for
discovering and controlling SmartRent devices.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, TypeAlias

from smartrent import (
    BinarySwitch,
    DoorLock,
    LeakSensor,
    MotionSensor,
    MultilevelSwitch,
    Thermostat,
    async_login,
)
from smartrent.api import API

logger = logging.getLogger(__name__)

SmartRentDevice: TypeAlias = (
    DoorLock | Thermostat | BinarySwitch | MultilevelSwitch | LeakSensor | MotionSensor
)


@dataclass
class DeviceInventory:
    """All SmartRent devices grouped by type."""

    locks: list[DoorLock] = field(default_factory=list)
    thermostats: list[Thermostat] = field(default_factory=list)
    binary_switches: list[BinarySwitch] = field(default_factory=list)
    multilevel_switches: list[MultilevelSwitch] = field(default_factory=list)
    leak_sensors: list[LeakSensor] = field(default_factory=list)
    motion_sensors: list[MotionSensor] = field(default_factory=list)

    @property
    def all_devices(self) -> list[SmartRentDevice]:
        """Return a flat list of every device."""
        return [
            *self.locks,
            *self.thermostats,
            *self.binary_switches,
            *self.multilevel_switches,
            *self.leak_sensors,
            *self.motion_sensors,
        ]

    @property
    def count(self) -> int:
        return len(self.all_devices)


class SmartRentClient:
    """High-level wrapper around smartrent-py.

    Handles login, device discovery, websocket updater lifecycle, and
    provides typed accessors for each device category.

    Args:
        email: SmartRent account email.
        password: SmartRent account password.
    """

    def __init__(self, email: str, password: str) -> None:
        self._email = email
        self._password = password
        self._api: API | None = None
        self._inventory: DeviceInventory | None = None
        self._updaters_running: bool = False

    @property
    def is_connected(self) -> bool:
        return self._api is not None

    @property
    def inventory(self) -> DeviceInventory:
        """Return the device inventory. Raises if not connected."""
        if self._inventory is None:
            raise RuntimeError("Not connected. Call connect() first.")
        return self._inventory

    async def connect(self) -> DeviceInventory:
        """Log in to SmartRent and fetch all devices.

        Returns:
            A ``DeviceInventory`` with all discovered devices.
        """
        logger.info("Logging in to SmartRent as %s", self._email)
        self._api = await async_login(self._email, self._password)

        self._inventory = DeviceInventory(
            locks=self._api.get_locks(),
            thermostats=self._api.get_thermostats(),
            binary_switches=self._api.get_binary_switches(),
            multilevel_switches=self._api.get_multilevel_switches(),
            leak_sensors=self._api.get_leak_sensors(),
            motion_sensors=self._api.get_motion_sensors(),
        )

        logger.info(
            "SmartRent connected: %d device(s) — %d lock(s), %d thermostat(s), "
            "%d binary switch(es), %d multilevel switch(es), %d leak sensor(s), "
            "%d motion sensor(s)",
            self._inventory.count,
            len(self._inventory.locks),
            len(self._inventory.thermostats),
            len(self._inventory.binary_switches),
            len(self._inventory.multilevel_switches),
            len(self._inventory.leak_sensors),
            len(self._inventory.motion_sensors),
        )

        return self._inventory

    def get_thermostats(self) -> list[Thermostat]:
        """Return all discovered thermostats."""
        return self.inventory.thermostats

    def get_locks(self) -> list[DoorLock]:
        """Return all discovered locks."""
        return self.inventory.locks

    def get_binary_switches(self) -> list[BinarySwitch]:
        """Return all discovered binary switches."""
        return self.inventory.binary_switches

    def get_multilevel_switches(self) -> list[MultilevelSwitch]:
        """Return all discovered multilevel switches."""
        return self.inventory.multilevel_switches

    def get_leak_sensors(self) -> list[LeakSensor]:
        """Return all discovered leak sensors."""
        return self.inventory.leak_sensors

    def get_motion_sensors(self) -> list[MotionSensor]:
        """Return all discovered motion sensors."""
        return self.inventory.motion_sensors

    def start_updaters(self) -> None:
        """Start websocket updaters on all discovered devices."""
        if self._updaters_running:
            return

        for device in self.inventory.all_devices:
            device.start_updater()

        self._updaters_running = True
        logger.info("Started updaters for %d device(s)", self.inventory.count)

    def stop_updaters(self) -> None:
        """Stop websocket updaters on all discovered devices."""
        if not self._updaters_running:
            return

        for device in self.inventory.all_devices:
            device.stop_updater()

        self._updaters_running = False
        logger.info("Stopped updaters for %d device(s)", self.inventory.count)

    def set_update_callback(self, callback: Any) -> None:
        """Register a callback on all devices for push updates.

        Args:
            callback: A sync or async callable invoked when any device state changes.
        """
        for device in self.inventory.all_devices:
            device.set_update_callback(callback)

    async def disconnect(self) -> None:
        """Stop updaters and clear state."""
        self.stop_updaters()
        self._api = None
        self._inventory = None
        logger.info("SmartRent disconnected")
