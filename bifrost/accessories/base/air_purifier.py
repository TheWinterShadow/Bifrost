"""Base skeleton for an air purifier accessory."""

from pyhap.accessory import Accessory
from pyhap.const import CATEGORY_AIR_PURIFIER


class AirPurifierCurrentState:
    """Valid values for CurrentAirPurifierState."""

    INACTIVE = 0
    IDLE = 1
    PURIFYING = 2


class AirPurifierTargetState:
    """Valid values for TargetAirPurifierState."""

    MANUAL = 0
    AUTO = 1


class AirQuality:
    """Valid values for AirQuality characteristic."""

    UNKNOWN = 0
    EXCELLENT = 1
    GOOD = 2
    FAIR = 3
    INFERIOR = 4
    POOR = 5


class FilterChangeIndication:
    """Valid values for FilterChangeIndication characteristic."""

    OK = 0
    CHANGE = 1


class AirPurifier(Accessory):
    """An air purifier with active toggle, current/target state, and optional speed.

    Linked services (filter maintenance, air quality sensor, humidity/temperature
    sensors) are added when the corresponding ``has_*`` flag is ``True``.

    Subclass this and implement ``_fetch_state``, ``_set_active``,
    ``_set_target_state``, and ``_set_rotation_speed`` for a specific
    device integration.
    """

    category = CATEGORY_AIR_PURIFIER

    def __init__(
        self,
        driver,
        name: str,
        *,
        has_filter_maintenance: bool = False,
        has_air_quality_sensor: bool = False,
        has_humidity_sensor: bool = False,
        has_temperature_sensor: bool = False,
    ) -> None:
        super().__init__(driver, name)

        # -- Primary AirPurifier service --
        svc = self.add_preload_service(
            "AirPurifier",
            chars=[
                "Active",
                "CurrentAirPurifierState",
                "TargetAirPurifierState",
                "RotationSpeed",
            ],
        )

        self.char_active = svc.configure_char(
            "Active",
            setter_callback=self._set_active,
        )
        self.char_current_state = svc.configure_char("CurrentAirPurifierState")
        self.char_target_state = svc.configure_char(
            "TargetAirPurifierState",
            setter_callback=self._set_target_state,
        )
        self.char_rotation_speed = svc.configure_char(
            "RotationSpeed",
            setter_callback=self._set_rotation_speed,
        )

        # -- Linked: Filter Maintenance --
        self.char_filter_change: None = None
        self.char_filter_life: None = None
        if has_filter_maintenance:
            filter_svc = self.add_preload_service(
                "FilterMaintenance",
                chars=["FilterChangeIndication", "FilterLifeLevel"],
            )
            svc.add_linked_service(filter_svc)
            self.char_filter_change = filter_svc.configure_char("FilterChangeIndication")
            self.char_filter_life = filter_svc.configure_char("FilterLifeLevel")

        # -- Linked: Air Quality Sensor --
        self.char_air_quality: None = None
        self.char_pm25: None = None
        if has_air_quality_sensor:
            aq_svc = self.add_preload_service(
                "AirQualitySensor",
                chars=["AirQuality", "PM2.5Density"],
            )
            svc.add_linked_service(aq_svc)
            self.char_air_quality = aq_svc.configure_char("AirQuality")
            self.char_pm25 = aq_svc.configure_char("PM2.5Density")

        # -- Linked: Humidity Sensor --
        self.char_humidity: None = None
        if has_humidity_sensor:
            humidity_svc = self.add_preload_service("HumiditySensor")
            svc.add_linked_service(humidity_svc)
            self.char_humidity = humidity_svc.configure_char("CurrentRelativeHumidity")

        # -- Linked: Temperature Sensor --
        self.char_temperature: None = None
        if has_temperature_sensor:
            temp_svc = self.add_preload_service("TemperatureSensor")
            svc.add_linked_service(temp_svc)
            self.char_temperature = temp_svc.configure_char("CurrentTemperature")

    # -- HomeKit -> device ---------------------------------------------------------

    def _set_active(self, value: int) -> None:
        """Called when HomeKit toggles the purifier on (1) or off (0)."""
        raise NotImplementedError

    def _set_target_state(self, value: int) -> None:
        """Called when HomeKit sets the target state.

        Args:
            value: One of ``AirPurifierTargetState.MANUAL`` or ``AUTO``.
        """
        raise NotImplementedError

    def _set_rotation_speed(self, value: float) -> None:
        """Called when HomeKit sets fan/rotation speed (0-100)."""
        raise NotImplementedError

    # -- device -> HomeKit ---------------------------------------------------------

    @Accessory.run_at_interval(30)
    async def run(self) -> None:
        """Poll the device and push current state to HomeKit."""
        state = await self._fetch_state()
        self.char_active.set_value(state.active)
        self.char_current_state.set_value(state.current_state)
        self.char_target_state.set_value(state.target_state)
        self.char_rotation_speed.set_value(state.rotation_speed)

        if self.char_filter_change is not None and state.filter_change is not None:
            self.char_filter_change.set_value(state.filter_change)
        if self.char_filter_life is not None and state.filter_life is not None:
            self.char_filter_life.set_value(state.filter_life)
        if self.char_air_quality is not None and state.air_quality is not None:
            self.char_air_quality.set_value(state.air_quality)
        if self.char_pm25 is not None and state.pm25_density is not None:
            self.char_pm25.set_value(state.pm25_density)
        if self.char_humidity is not None and state.humidity is not None:
            self.char_humidity.set_value(state.humidity)
        if self.char_temperature is not None and state.temperature is not None:
            self.char_temperature.set_value(state.temperature)

    async def _fetch_state(self) -> "AirPurifierState":
        """Return current state from the real device.

        Returns:
            An ``AirPurifierState`` instance with all fields populated.
        """
        raise NotImplementedError


class AirPurifierState:
    """Container for air purifier state returned by ``_fetch_state``.

    Args:
        active: 1 if active, 0 if inactive.
        current_state: One of ``AirPurifierCurrentState`` values.
        target_state: One of ``AirPurifierTargetState`` values.
        rotation_speed: Fan speed percentage (0-100).
        filter_change: ``FilterChangeIndication`` value, or ``None`` if unsupported.
        filter_life: Filter life remaining (0-100%), or ``None`` if unsupported.
        air_quality: ``AirQuality`` value, or ``None`` if unsupported.
        pm25_density: PM2.5 density in µg/m³, or ``None`` if unsupported.
        humidity: Relative humidity percentage, or ``None`` if unsupported.
        temperature: Temperature in Celsius, or ``None`` if unsupported.
    """

    __slots__ = (
        "active",
        "air_quality",
        "current_state",
        "filter_change",
        "filter_life",
        "humidity",
        "pm25_density",
        "rotation_speed",
        "target_state",
        "temperature",
    )

    def __init__(
        self,
        *,
        active: int,
        current_state: int,
        target_state: int,
        rotation_speed: float = 0,
        filter_change: int | None = None,
        filter_life: float | None = None,
        air_quality: int | None = None,
        pm25_density: float | None = None,
        humidity: float | None = None,
        temperature: float | None = None,
    ) -> None:
        self.active = active
        self.current_state = current_state
        self.target_state = target_state
        self.rotation_speed = rotation_speed
        self.filter_change = filter_change
        self.filter_life = filter_life
        self.air_quality = air_quality
        self.pm25_density = pm25_density
        self.humidity = humidity
        self.temperature = temperature
