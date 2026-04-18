"""Govee light accessory."""

import asyncio
import logging
import random
from typing import Any

from pyhap.accessory_driver import AccessoryDriver

from bifrost.accessories.base.light import (
    ColorMode,
    Light,
    LightState,
    hsv_to_rgb,
    kelvin_to_mireds,
    mireds_to_kelvin,
    rgb_to_hsv,
)
from bifrost.utils.govee import GoveeClient

logger = logging.getLogger(__name__)

POLL_INTERVAL = 30


class GoveeLight(Light):
    """A Govee light with on/off, brightness, and optional color/temperature control."""

    def __init__(
        self,
        driver: AccessoryDriver,
        name: str,
        *,
        client: GoveeClient,
        sku: str,
        device_id: str,
        has_color: bool = False,
        has_color_temp: bool = False,
    ) -> None:
        super().__init__(driver, name, has_color=has_color, has_color_temp=has_color_temp)
        self._client = client
        self._sku = sku
        self._device_id = device_id
        self._poll_offset = random.uniform(0, 25)
        self._color_mode = ColorMode.TEMPERATURE
        logger.info("Registered light: %s (sku=%s device=%s)", name, sku, device_id)

    # -- HomeKit -> device ---------------------------------------------------------

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

    def _set_color(self, hue: float, saturation: float) -> None:
        logger.info("%s: setting color hue=%s sat=%s", self.display_name, hue, saturation)
        self._color_mode = ColorMode.COLOR
        if self.char_hue is not None:
            self.char_hue.set_value(hue)
        if self.char_saturation is not None:
            self.char_saturation.set_value(saturation)
        brightness = self.char_brightness.get_value() if self.char_brightness else 100
        r, g, b = hsv_to_rgb(hue, saturation, brightness)
        self.driver.add_job(self._client.set_device_color, self._sku, self._device_id, r, g, b)

    def _set_color_temperature(self, value: int) -> None:
        logger.info("%s: setting color_temp=%s mireds", self.display_name, value)
        self._color_mode = ColorMode.TEMPERATURE
        if self.char_color_temp is not None:
            self.char_color_temp.set_value(value)
        kelvin = mireds_to_kelvin(value)
        self.driver.add_job(
            self._client.set_device_color_temperature, self._sku, self._device_id, kelvin
        )

    # -- device -> HomeKit ---------------------------------------------------------

    async def run(self) -> None:
        """Fetch state immediately, then poll every POLL_INTERVAL seconds."""
        await asyncio.sleep(self._poll_offset)
        while True:
            try:
                state = await self._fetch_state()
                logger.info(
                    "%s: polled state on=%s brightness=%s hue=%s sat=%s temp=%s mode=%s",
                    self.display_name,
                    state.on,
                    state.brightness,
                    state.hue,
                    state.saturation,
                    state.color_temp,
                    state.color_mode,
                )
                self.char_on.set_value(state.on)
                self.char_brightness.set_value(state.brightness)
                if self.char_hue is not None and state.hue is not None:
                    self.char_hue.set_value(state.hue)
                if self.char_saturation is not None and state.saturation is not None:
                    self.char_saturation.set_value(state.saturation)
                if self.char_color_temp is not None and state.color_temp is not None:
                    self.char_color_temp.set_value(state.color_temp)
                if state.color_mode is not None:
                    self._color_mode = state.color_mode
            except Exception:
                logger.exception("%s: failed to fetch state", self.display_name)
            await asyncio.sleep(POLL_INTERVAL)

    async def _fetch_state(self) -> LightState:
        loop = self.driver.loop
        response = await loop.run_in_executor(
            None, self._client.get_device_state, self._sku, self._device_id
        )
        logger.debug("%s: raw state response: %s", self.display_name, response)
        return _parse_capabilities(response["payload"]["capabilities"])


def _parse_capabilities(capabilities: list[dict[str, Any]]) -> LightState:
    """Extract light state from a Govee capabilities list.

    Govee lights expose:
    - ``powerSwitch`` (0/1)
    - ``brightness`` (0-100 or 0-254 scale)
    - ``colorRgb`` (packed 24-bit integer, e.g. 16711680 = red)
    - ``colorTemInKelvin`` (integer Kelvin value)

    Some Govee devices report brightness on a 0-254 scale instead of 0-100.
    Values above 100 are normalised to the 0-100 range HomeKit requires.
    """
    caps = {c["instance"]: c["state"]["value"] for c in capabilities}
    on = bool(caps.get("powerSwitch", 0))
    raw_brightness = int(caps.get("brightness", 100))
    brightness = round(raw_brightness / 254 * 100) if raw_brightness > 100 else raw_brightness

    hue: float | None = None
    saturation: float | None = None
    color_temp: int | None = None
    color_mode: str | None = None

    if "colorRgb" in caps:
        packed = int(caps["colorRgb"])
        r = (packed >> 16) & 0xFF
        g = (packed >> 8) & 0xFF
        b = packed & 0xFF
        hue, saturation, _ = rgb_to_hsv(r, g, b)
        color_mode = ColorMode.COLOR

    if "colorTemInKelvin" in caps:
        kelvin = int(caps["colorTemInKelvin"])
        if kelvin > 0:
            color_temp = kelvin_to_mireds(kelvin)
            # If temp is present and color is not, or if temp is clearly active
            # (non-zero kelvin typically means the device is in temp mode)
            if color_mode is None:
                color_mode = ColorMode.TEMPERATURE

    return LightState(
        on=on,
        brightness=brightness,
        hue=hue,
        saturation=saturation,
        color_temp=color_temp,
        color_mode=color_mode,
    )


def discover_lights(client: GoveeClient, driver: AccessoryDriver) -> list[GoveeLight]:
    """Return a GoveeLight for every device in the Govee account.

    Inspects each device's capability list to determine whether color and
    color-temperature controls should be enabled.
    """
    logger.info("Discovering Govee lights...")
    lights: list[GoveeLight] = []
    for device in client.get_lights():
        cap_types = {c.get("instance", "") for c in device.get("capabilities", [])}
        light = GoveeLight(
            driver,
            device["deviceName"],
            client=client,
            sku=device["sku"],
            device_id=device["device"],
            has_color="colorRgb" in cap_types,
            has_color_temp="colorTemInKelvin" in cap_types,
        )
        lights.append(light)
    logger.info("Discovered %d light(s)", len(lights))
    return lights
