"""Base skeleton for a thermostat accessory."""

from pyhap.accessory import Accessory
from pyhap.const import CATEGORY_THERMOSTAT


class HeatingCoolingState:
    """Valid values for CurrentHeatingCoolingState and TargetHeatingCoolingState."""

    OFF = 0
    HEAT = 1
    COOL = 2
    AUTO = 3  # TargetHeatingCoolingState only


class TemperatureUnit:
    """Valid values for TemperatureDisplayUnits."""

    CELSIUS = 0
    FAHRENHEIT = 1


class Thermostat(Accessory):
    """A thermostat with heating/cooling mode, target temperature, and display units.

    Subclass this and implement ``_fetch_state``, ``_set_target_temperature``,
    ``_set_target_heating_cooling_state``, and ``_set_temperature_display_units``
    for a specific device integration.
    """

    category = CATEGORY_THERMOSTAT

    def __init__(self, driver, name: str) -> None:
        super().__init__(driver, name)

        svc = self.add_preload_service(
            "Thermostat",
            chars=[
                "CurrentHeatingCoolingState",
                "TargetHeatingCoolingState",
                "CurrentTemperature",
                "TargetTemperature",
                "TemperatureDisplayUnits",
            ],
        )

        self.char_current_heating_cooling = svc.configure_char(
            "CurrentHeatingCoolingState",
        )
        self.char_target_heating_cooling = svc.configure_char(
            "TargetHeatingCoolingState",
            setter_callback=self._set_target_heating_cooling_state,
        )
        self.char_current_temp = svc.configure_char("CurrentTemperature")
        self.char_target_temp = svc.configure_char(
            "TargetTemperature",
            setter_callback=self._set_target_temperature,
        )
        self.char_display_units = svc.configure_char(
            "TemperatureDisplayUnits",
            setter_callback=self._set_temperature_display_units,
        )

    # -- HomeKit -> device ---------------------------------------------------------

    def _set_target_heating_cooling_state(self, value: int) -> None:
        """Called when HomeKit sets the target heating/cooling mode.

        Args:
            value: One of ``HeatingCoolingState.OFF``, ``HEAT``, ``COOL``, or ``AUTO``.
        """
        raise NotImplementedError

    def _set_target_temperature(self, value: float) -> None:
        """Called when HomeKit sets the target temperature (Celsius)."""
        raise NotImplementedError

    def _set_temperature_display_units(self, value: int) -> None:
        """Called when HomeKit changes temperature display units.

        Args:
            value: One of ``TemperatureUnit.CELSIUS`` or ``FAHRENHEIT``.
        """
        raise NotImplementedError

    # -- device -> HomeKit ---------------------------------------------------------

    @Accessory.run_at_interval(30)
    async def run(self) -> None:
        """Poll the device and push current state to HomeKit."""
        state = await self._fetch_state()
        self.char_current_heating_cooling.set_value(state.current_mode)
        self.char_target_heating_cooling.set_value(state.target_mode)
        self.char_current_temp.set_value(state.current_temp)
        self.char_target_temp.set_value(state.target_temp)
        self.char_display_units.set_value(state.display_units)

    async def _fetch_state(self) -> "ThermostatState":
        """Return current state from the real device.

        Returns:
            A ``ThermostatState`` instance with all fields populated.
        """
        raise NotImplementedError


class ThermostatState:
    """Simple container for thermostat state returned by ``_fetch_state``.

    Args:
        current_mode: Current heating/cooling state (OFF, HEAT, COOL).
        target_mode: Target heating/cooling state (OFF, HEAT, COOL, AUTO).
        current_temp: Current temperature in Celsius.
        target_temp: Target temperature in Celsius.
        display_units: Temperature display units (CELSIUS or FAHRENHEIT).
    """

    __slots__ = (
        "current_mode",
        "current_temp",
        "display_units",
        "target_mode",
        "target_temp",
    )

    def __init__(
        self,
        *,
        current_mode: int,
        target_mode: int,
        current_temp: float,
        target_temp: float,
        display_units: int = TemperatureUnit.CELSIUS,
    ) -> None:
        self.current_mode = current_mode
        self.target_mode = target_mode
        self.current_temp = current_temp
        self.target_temp = target_temp
        self.display_units = display_units
