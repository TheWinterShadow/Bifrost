"""Base skeleton for a dimmable light accessory."""

import colorsys

from pyhap.accessory import Accessory
from pyhap.const import CATEGORY_LIGHTBULB


class ColorMode:
    """Tracks whether the light is in color (HSV) or color temperature mode."""

    COLOR = "color"
    TEMPERATURE = "temperature"


class Light(Accessory):
    """A dimmable light bulb with optional color and color temperature support.

    Subclass this and implement ``_fetch_state``, ``_set_on``, and
    ``_set_brightness`` for a specific device integration. When color or color
    temperature is enabled, also implement ``_set_color`` and/or
    ``_set_color_temperature``.
    """

    category = CATEGORY_LIGHTBULB

    def __init__(
        self,
        driver,
        name: str,
        *,
        has_color: bool = False,
        has_color_temp: bool = False,
    ) -> None:
        super().__init__(driver, name)

        chars = ["On", "Brightness"]
        if has_color:
            chars += ["Hue", "Saturation"]
        if has_color_temp:
            chars.append("ColorTemperature")

        svc = self.add_preload_service("Lightbulb", chars=chars)
        self.char_on = svc.configure_char("On", setter_callback=self._set_on)
        self.char_brightness = svc.configure_char(
            "Brightness", setter_callback=self._set_brightness
        )

        self.char_hue: None = None
        self.char_saturation: None = None
        if has_color:
            self.char_hue = svc.configure_char("Hue", setter_callback=self._set_hue)
            self.char_saturation = svc.configure_char(
                "Saturation", setter_callback=self._set_saturation
            )

        self.char_color_temp: None = None
        if has_color_temp:
            self.char_color_temp = svc.configure_char(
                "ColorTemperature", setter_callback=self._set_color_temperature
            )

    # -- HomeKit -> device ---------------------------------------------------------

    def _set_on(self, value: bool) -> None:
        """Called when HomeKit turns the light on or off."""
        raise NotImplementedError

    def _set_brightness(self, value: int) -> None:
        """Called when HomeKit changes brightness (0-100)."""
        raise NotImplementedError

    def _set_hue(self, value: float) -> None:
        """Called when HomeKit changes hue (0-360).

        Default implementation calls ``_set_color`` with current hue/saturation.
        Override for custom behavior.
        """
        self._set_color(value, self.char_saturation.get_value())

    def _set_saturation(self, value: float) -> None:
        """Called when HomeKit changes saturation (0-100).

        Default implementation calls ``_set_color`` with current hue/saturation.
        Override for custom behavior.
        """
        self._set_color(self.char_hue.get_value(), value)

    def _set_color(self, hue: float, saturation: float) -> None:
        """Called when HomeKit changes color via hue or saturation.

        Args:
            hue: Hue in degrees (0-360).
            saturation: Saturation percentage (0-100).
        """
        raise NotImplementedError

    def _set_color_temperature(self, value: int) -> None:
        """Called when HomeKit changes color temperature (mireds, 140-500)."""
        raise NotImplementedError

    # -- device -> HomeKit ---------------------------------------------------------

    @Accessory.run_at_interval(30)
    async def run(self) -> None:
        """Poll the device and push current state to HomeKit."""
        state = await self._fetch_state()
        self.char_on.set_value(state.on)
        self.char_brightness.set_value(state.brightness)
        if self.char_hue is not None and state.hue is not None:
            self.char_hue.set_value(state.hue)
        if self.char_saturation is not None and state.saturation is not None:
            self.char_saturation.set_value(state.saturation)
        if self.char_color_temp is not None and state.color_temp is not None:
            self.char_color_temp.set_value(state.color_temp)

    async def _fetch_state(self) -> "LightState":
        """Return current state from the real device."""
        raise NotImplementedError


class LightState:
    """Container for light state returned by ``_fetch_state``.

    Args:
        on: Whether the light is on.
        brightness: Brightness percentage (0-100).
        hue: Hue in degrees (0-360), or ``None`` if not a color light.
        saturation: Saturation percentage (0-100), or ``None``.
        color_temp: Color temperature in mireds (140-500), or ``None``.
        color_mode: Which mode the light is currently in (``ColorMode``).
    """

    __slots__ = ("brightness", "color_mode", "color_temp", "hue", "on", "saturation")

    def __init__(
        self,
        *,
        on: bool,
        brightness: int,
        hue: float | None = None,
        saturation: float | None = None,
        color_temp: int | None = None,
        color_mode: str | None = None,
    ) -> None:
        self.on = on
        self.brightness = brightness
        self.hue = hue
        self.saturation = saturation
        self.color_temp = color_temp
        self.color_mode = color_mode


def hsv_to_rgb(hue: float, saturation: float, brightness: float) -> tuple[int, int, int]:
    """Convert HomeKit HSV values to 0-255 RGB.

    Args:
        hue: 0-360 degrees.
        saturation: 0-100 percent.
        brightness: 0-100 percent.

    Returns:
        (r, g, b) tuple with values 0-255.
    """
    r, g, b = colorsys.hsv_to_rgb(hue / 360, saturation / 100, brightness / 100)
    return round(r * 255), round(g * 255), round(b * 255)


def rgb_to_hsv(r: int, g: int, b: int) -> tuple[float, float, float]:
    """Convert 0-255 RGB to HomeKit HSV values.

    Returns:
        (hue 0-360, saturation 0-100, brightness 0-100).
    """
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    return round(h * 360), round(s * 100), round(v * 100)


def kelvin_to_mireds(kelvin: int) -> int:
    """Convert color temperature from Kelvin to mireds."""
    if kelvin <= 0:
        return 500
    return max(140, min(500, round(1_000_000 / kelvin)))


def mireds_to_kelvin(mireds: int) -> int:
    """Convert color temperature from mireds to Kelvin."""
    if mireds <= 0:
        return 7143
    return round(1_000_000 / mireds)
