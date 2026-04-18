"""Govee air purifier accessory."""

import asyncio
import logging
import random
from typing import Any

from pyhap.accessory_driver import AccessoryDriver

from bifrost.accessories.base.air_purifier import (
    AirPurifier,
    AirPurifierCurrentState,
    AirPurifierState,
    AirPurifierTargetState,
)
from bifrost.utils.govee import GoveeClient

logger = logging.getLogger(__name__)

POLL_INTERVAL = 30

# Govee work modes for air purifiers (from device capability descriptors).
# Exact values vary by SKU, but these are the common ones across H713x series.
GOVEE_MODE_MANUAL = 1
GOVEE_MODE_AUTO = 2
GOVEE_MODE_SLEEP = 3

# Maximum fan gear value reported by most Govee air purifiers.
GOVEE_MAX_GEAR = 4


class GoveeAirPurifier(AirPurifier):
    """A Govee air purifier exposed to HomeKit."""

    def __init__(
        self,
        driver: AccessoryDriver,
        name: str,
        *,
        client: GoveeClient,
        sku: str,
        device_id: str,
    ) -> None:
        super().__init__(driver, name)
        self._client = client
        self._sku = sku
        self._device_id = device_id
        self._poll_offset = random.uniform(0, 25)
        logger.info("Registered air purifier: %s (sku=%s device=%s)", name, sku, device_id)

    # -- HomeKit -> device ---------------------------------------------------------

    def _set_active(self, value: int) -> None:
        logger.info("%s: setting active=%s", self.display_name, value)
        self.char_active.set_value(value)
        if value:
            self.driver.add_job(self._client.turn_on_device, self._sku, self._device_id)
        else:
            self.driver.add_job(self._client.turn_off_device, self._sku, self._device_id)

    def _set_target_state(self, value: int) -> None:
        logger.info("%s: setting target_state=%s", self.display_name, value)
        self.char_target_state.set_value(value)
        if value == AirPurifierTargetState.AUTO:
            self.driver.add_job(
                self._client.set_device_mode, self._sku, self._device_id, GOVEE_MODE_AUTO
            )
        else:
            # Manual mode — keep current gear
            self.driver.add_job(
                self._client.set_device_mode, self._sku, self._device_id, GOVEE_MODE_MANUAL
            )

    def _set_rotation_speed(self, value: float) -> None:
        logger.info("%s: setting rotation_speed=%s", self.display_name, value)
        self.char_rotation_speed.set_value(value)
        gear = _percent_to_gear(value)
        self.driver.add_job(
            self._client.set_device_mode, self._sku, self._device_id, GOVEE_MODE_MANUAL, gear
        )

    # -- device -> HomeKit ---------------------------------------------------------

    async def run(self) -> None:
        """Fetch state immediately, then poll every POLL_INTERVAL seconds."""
        await asyncio.sleep(self._poll_offset)
        while True:
            try:
                state = await self._fetch_state()
                logger.info(
                    "%s: polled state active=%s current=%s target=%s speed=%s",
                    self.display_name,
                    state.active,
                    state.current_state,
                    state.target_state,
                    state.rotation_speed,
                )
                self.char_active.set_value(state.active)
                self.char_current_state.set_value(state.current_state)
                self.char_target_state.set_value(state.target_state)
                self.char_rotation_speed.set_value(state.rotation_speed)
            except Exception:
                logger.exception("%s: failed to fetch state", self.display_name)
            await asyncio.sleep(POLL_INTERVAL)

    async def _fetch_state(self) -> AirPurifierState:
        loop = self.driver.loop
        response = await loop.run_in_executor(
            None, self._client.get_device_state, self._sku, self._device_id
        )
        logger.debug("%s: raw state response: %s", self.display_name, response)
        return _parse_capabilities(response["payload"]["capabilities"])


def _parse_capabilities(capabilities: list[dict[str, Any]]) -> AirPurifierState:
    """Extract air purifier state from a Govee capabilities list.

    Govee air purifiers expose:
    - ``powerSwitch`` (0/1)
    - ``workMode`` with ``workMode`` and ``modeValue`` sub-fields
    """
    caps = {c["instance"]: c["state"]["value"] for c in capabilities}

    on = bool(caps.get("powerSwitch", 0))

    work_mode_raw = caps.get("workMode", {})
    if isinstance(work_mode_raw, dict):
        govee_mode = work_mode_raw.get("workMode", GOVEE_MODE_MANUAL)
        mode_value = work_mode_raw.get("modeValue", 0)
    else:
        govee_mode = GOVEE_MODE_MANUAL
        mode_value = 0

    if not on:
        current_state = AirPurifierCurrentState.INACTIVE
        target_state = AirPurifierTargetState.MANUAL
        rotation_speed = 0.0
    elif govee_mode == GOVEE_MODE_AUTO:
        current_state = AirPurifierCurrentState.PURIFYING
        target_state = AirPurifierTargetState.AUTO
        rotation_speed = _gear_to_percent(mode_value)
    else:
        current_state = AirPurifierCurrentState.PURIFYING
        target_state = AirPurifierTargetState.MANUAL
        rotation_speed = _gear_to_percent(mode_value)

    return AirPurifierState(
        active=int(on),
        current_state=current_state,
        target_state=target_state,
        rotation_speed=rotation_speed,
    )


def _gear_to_percent(gear: int, max_gear: int = GOVEE_MAX_GEAR) -> float:
    """Convert a Govee gear value (1-N) to a HomeKit percentage (0-100)."""
    if gear <= 0:
        return 0.0
    return round(gear / max_gear * 100)


def _percent_to_gear(percent: float, max_gear: int = GOVEE_MAX_GEAR) -> int:
    """Convert a HomeKit percentage (0-100) to a Govee gear value (1-N)."""
    if percent <= 0:
        return 1
    return max(1, min(max_gear, round(percent / 100 * max_gear)))


def discover_air_purifiers(client: GoveeClient, driver: AccessoryDriver) -> list[GoveeAirPurifier]:
    """Return a GoveeAirPurifier for every air purifier in the Govee account."""
    logger.info("Discovering Govee air purifiers...")
    purifiers: list[GoveeAirPurifier] = []
    for device in client.get_air_purifiers():
        purifier = GoveeAirPurifier(
            driver,
            device["deviceName"],
            client=client,
            sku=device["sku"],
            device_id=device["device"],
        )
        purifiers.append(purifier)
    logger.info("Discovered %d air purifier(s)", len(purifiers))
    return purifiers
