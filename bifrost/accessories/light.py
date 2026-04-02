"""Base skeleton for a dimmable light accessory."""

from pyhap.accessory import Accessory
from pyhap.const import CATEGORY_LIGHTBULB


class Light(Accessory):
    """A dimmable light bulb.

    Subclass this and implement `_fetch_state`, `_send_on`, and
    `_send_brightness` for a specific device integration.
    """

    category = CATEGORY_LIGHTBULB

    def __init__(self, driver, name: str) -> None:
        super().__init__(driver, name)

        svc = self.add_preload_service("Lightbulb", chars=["On", "Brightness"])
        self.char_on = svc.configure_char("On", setter_callback=self._set_on)
        self.char_brightness = svc.configure_char(
            "Brightness", setter_callback=self._set_brightness
        )

    # ── HomeKit → device ─────────────────────────────────────────────────────

    def _set_on(self, value: bool) -> None:
        """Called when HomeKit turns the light on or off."""
        raise NotImplementedError

    def _set_brightness(self, value: int) -> None:
        """Called when HomeKit changes brightness (0–100)."""
        raise NotImplementedError

    # ── device → HomeKit ─────────────────────────────────────────────────────

    @Accessory.run_at_interval(30)
    async def run(self) -> None:
        """Poll the device and push current state to HomeKit."""
        on, brightness = await self._fetch_state()
        self.char_on.set_value(on)
        self.char_brightness.set_value(brightness)

    async def _fetch_state(self) -> tuple[bool, int]:
        """Return (on, brightness) from the real device."""
        raise NotImplementedError
