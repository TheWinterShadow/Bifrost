"""SmartRent thermostat accessory."""

import asyncio
import logging

from pyhap.accessory_driver import AccessoryDriver
from smartrent import Thermostat as SRThermostat

from bifrost.accessories.base.thermostat import (
    HeatingCoolingState,
    TemperatureUnit,
    Thermostat,
    ThermostatState,
)

logger = logging.getLogger(__name__)

POLL_INTERVAL = 60

# SmartRent mode strings → HAP TargetHeatingCoolingState
_SR_MODE_TO_HAP_TARGET: dict[str, int] = {
    "off": HeatingCoolingState.OFF,
    "heat": HeatingCoolingState.HEAT,
    "aux_heat": HeatingCoolingState.HEAT,
    "cool": HeatingCoolingState.COOL,
    "auto": HeatingCoolingState.AUTO,
}

# HAP TargetHeatingCoolingState → SmartRent mode string
_HAP_TARGET_TO_SR_MODE: dict[int, str] = {
    HeatingCoolingState.OFF: "off",
    HeatingCoolingState.HEAT: "heat",
    HeatingCoolingState.COOL: "cool",
    HeatingCoolingState.AUTO: "auto",
}

# SmartRent operating_state → HAP CurrentHeatingCoolingState
_SR_OPSTATE_TO_HAP_CURRENT: dict[str, int] = {
    "off": HeatingCoolingState.OFF,
    "idle": HeatingCoolingState.OFF,
    "heating": HeatingCoolingState.HEAT,
    "cooling": HeatingCoolingState.COOL,
}


def f_to_c(fahrenheit: int | float) -> float:
    """Convert Fahrenheit to Celsius, rounded to one decimal."""
    return round((fahrenheit - 32) * 5 / 9, 1)


def c_to_f(celsius: float) -> int:
    """Convert Celsius to Fahrenheit, rounded to nearest integer."""
    return round(celsius * 9 / 5 + 32)


def sr_mode_to_hap_target(mode: str | None) -> int:
    """Map a SmartRent mode string to a HAP TargetHeatingCoolingState value."""
    return _SR_MODE_TO_HAP_TARGET.get(mode or "off", HeatingCoolingState.OFF)


def hap_target_to_sr_mode(value: int) -> str:
    """Map a HAP TargetHeatingCoolingState value to a SmartRent mode string."""
    return _HAP_TARGET_TO_SR_MODE.get(value, "off")


def sr_opstate_to_hap_current(operating_state: str | None) -> int:
    """Map a SmartRent operating_state to a HAP CurrentHeatingCoolingState value."""
    return _SR_OPSTATE_TO_HAP_CURRENT.get(operating_state or "off", HeatingCoolingState.OFF)


def target_temp_for_mode(
    mode: str | None,
    heating_setpoint: int | None,
    cooling_setpoint: int | None,
) -> float:
    """Pick the appropriate target temperature (Celsius) based on the current mode.

    In heat mode the heating setpoint is used. In cool mode the cooling
    setpoint is used. In auto mode the midpoint of the two setpoints is
    returned. Falls back to 20°C if setpoints are unavailable.
    """
    heat_c = f_to_c(heating_setpoint) if heating_setpoint is not None else 20.0
    cool_c = f_to_c(cooling_setpoint) if cooling_setpoint is not None else 20.0

    if mode in ("heat", "aux_heat"):
        return heat_c
    if mode == "cool":
        return cool_c
    if mode == "auto":
        return round((heat_c + cool_c) / 2, 1)
    return heat_c


class SmartRentThermostat(Thermostat):
    """A SmartRent thermostat exposed to HomeKit.

    Uses the smartrent-py ``Thermostat`` device object for reads and writes.
    Polling is done via ``run_in_executor`` to avoid blocking the event loop
    since smartrent-py getters are synchronous.

    Args:
        driver: The HAP accessory driver.
        name: Display name for the accessory.
        device: A smartrent-py ``Thermostat`` instance (already fetched).
    """

    def __init__(
        self,
        driver: AccessoryDriver,
        name: str,
        *,
        device: SRThermostat,
    ) -> None:
        super().__init__(driver, name)
        self._device = device
        logger.info(
            "Registered SmartRent thermostat: %s (id=%d)",
            name,
            device._device_id,
        )

    # -- HomeKit → device ----------------------------------------------------------

    def _set_target_heating_cooling_state(self, value: int) -> None:
        sr_mode = hap_target_to_sr_mode(value)
        logger.info("%s: setting mode=%s (HAP %d)", self.display_name, sr_mode, value)
        self.char_target_heating_cooling.set_value(value)
        self.driver.loop.create_task(self._device.async_set_mode(sr_mode))

    def _set_target_temperature(self, value: float) -> None:
        logger.info("%s: setting target_temp=%.1f°C", self.display_name, value)
        self.char_target_temp.set_value(value)
        temp_f = c_to_f(value)
        mode = self._device.get_mode()
        if mode in ("heat", "aux_heat"):
            self.driver.loop.create_task(self._device.async_set_heating_setpoint(temp_f))
        elif mode == "cool":
            self.driver.loop.create_task(self._device.async_set_cooling_setpoint(temp_f))
        else:
            self.driver.loop.create_task(self._device.async_set_heating_setpoint(temp_f))
            self.driver.loop.create_task(self._device.async_set_cooling_setpoint(temp_f))

    def _set_temperature_display_units(self, value: int) -> None:
        logger.info("%s: setting display_units=%d", self.display_name, value)
        self.char_display_units.set_value(value)

    # -- device → HomeKit ----------------------------------------------------------

    async def run(self) -> None:
        """Poll the SmartRent device and push state to HomeKit."""
        while True:
            try:
                state = await self._fetch_state()
                self.char_current_heating_cooling.set_value(state.current_mode)
                self.char_target_heating_cooling.set_value(state.target_mode)
                self.char_current_temp.set_value(state.current_temp)
                self.char_target_temp.set_value(state.target_temp)
                self.char_display_units.set_value(state.display_units)
                logger.info(
                    "%s: polled state current_mode=%d target_mode=%d "
                    "current_temp=%.1f target_temp=%.1f",
                    self.display_name,
                    state.current_mode,
                    state.target_mode,
                    state.current_temp,
                    state.target_temp,
                )
            except Exception:
                logger.exception("%s: failed to fetch state", self.display_name)
            await asyncio.sleep(POLL_INTERVAL)

    async def _fetch_state(self) -> ThermostatState:
        await self._device._async_fetch_state()

        mode = self._device.get_mode()
        return ThermostatState(
            current_mode=sr_opstate_to_hap_current(self._device.get_operating_state()),
            target_mode=sr_mode_to_hap_target(mode),
            current_temp=f_to_c(self._device.get_current_temp() or 68),
            target_temp=target_temp_for_mode(
                mode,
                self._device.get_heating_setpoint(),
                self._device.get_cooling_setpoint(),
            ),
            display_units=TemperatureUnit.FAHRENHEIT,
        )


def discover_thermostats(
    thermostats: list[SRThermostat],
    driver: AccessoryDriver,
) -> list[SmartRentThermostat]:
    """Return a SmartRentThermostat accessory for each SmartRent thermostat device.

    Args:
        thermostats: Pre-fetched smartrent-py Thermostat objects.
        driver: The HAP accessory driver.
    """
    logger.info("Discovering SmartRent thermostats...")
    accessories: list[SmartRentThermostat] = []
    for device in thermostats:
        name = device.get_name() or f"Thermostat {device._device_id}"
        accessories.append(SmartRentThermostat(driver, name, device=device))
    logger.info("Discovered %d SmartRent thermostat(s)", len(accessories))
    return accessories
