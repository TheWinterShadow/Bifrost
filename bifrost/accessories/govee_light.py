"""Govee light accessory."""

import asyncio
import logging
import random
from typing import Any

from pyhap.accessory_driver import AccessoryDriver

from bifrost.accessories.light import Light
from bifrost.utils.govee import GoveeClient

logger = logging.getLogger(__name__)

POLL_INTERVAL = 30


class GoveeLight(Light):
    """A Govee light with on/off control."""

    def __init__(
        self, driver: AccessoryDriver, name: str, *, client: GoveeClient, sku: str, device_id: str
    ) -> None:
        super().__init__(driver, name)
        self._client = client
        self._sku = sku
        self._device_id = device_id
        # Stagger polls so all lights don't hit the Govee API simultaneously
        self._poll_offset = random.uniform(0, 25)
        logger.info("Registered light: %s (sku=%s device=%s)", name, sku, device_id)

    # ── HomeKit → device ─────────────────────────────────────────────────────

    def _set_on(self, value: bool) -> None:
        logger.info("%s: setting on=%s", self.display_name, value)
        self.char_on.set_value(value)
        if value:
            self.driver.add_job(self._client.turn_on_device, self._sku, self._device_id)
        else:
            self.driver.add_job(self._client.turn_off_device, self._sku, self._device_id)

    def _set_brightness(self, value: int) -> None:
        logger.info("%s: setting brightness=%s", self.display_name, value)
        self.char_brightness.set_value(value)
        self.driver.add_job(self._client.set_device_brightness, self._sku, self._device_id, value)

    # ── device → HomeKit ─────────────────────────────────────────────────────

    async def run(self) -> None:
        """Fetch state immediately, then poll every POLL_INTERVAL seconds."""
        await asyncio.sleep(self._poll_offset)
        while True:
            try:
                on, brightness = await self._fetch_state()
                logger.info(
                    "%s: polled state on=%s brightness=%s", self.display_name, on, brightness
                )
                self.char_on.set_value(on)
                self.char_brightness.set_value(brightness)
            except Exception:
                logger.exception("%s: failed to fetch state", self.display_name)
            await asyncio.sleep(POLL_INTERVAL)

    async def _fetch_state(self) -> tuple[bool, int]:
        loop = self.driver.loop
        response = await loop.run_in_executor(
            None, self._client.get_device_state, self._sku, self._device_id
        )
        logger.debug("%s: raw state response: %s", self.display_name, response)
        return _parse_capabilities(response["payload"]["capabilities"])


def _parse_capabilities(capabilities: list[dict[str, Any]]) -> tuple[bool, int]:
    """Extract (on, brightness) from a Govee capabilities list."""
    caps = {c["instance"]: c["state"]["value"] for c in capabilities}
    return bool(caps.get("powerSwitch", 0)), int(caps.get("brightness", 100))


def discover_lights(client: GoveeClient, driver: AccessoryDriver) -> list[GoveeLight]:
    """Return a GoveeLight for every device in the Govee account."""
    logger.info("Discovering Govee lights...")
    lights: list[GoveeLight] = []
    for device in client.get_lights():
        light = GoveeLight(
            driver,
            device["deviceName"],
            client=client,
            sku=device["sku"],
            device_id=device["device"],
        )
        lights.append(light)
    logger.info("Discovered %d light(s)", len(lights))
    return lights
