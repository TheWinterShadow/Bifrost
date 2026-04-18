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


class AirPurifier(Accessory):
    """An air purifier with active toggle, current/target state, and optional speed.

    Subclass this and implement ``_fetch_state``, ``_set_active``,
    ``_set_target_state``, and ``_set_rotation_speed`` for a specific
    device integration.
    """

    category = CATEGORY_AIR_PURIFIER

    def __init__(self, driver, name: str) -> None:
        super().__init__(driver, name)

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

    async def _fetch_state(self) -> "AirPurifierState":
        """Return current state from the real device.

        Returns:
            An ``AirPurifierState`` instance with all fields populated.
        """
        raise NotImplementedError


class AirPurifierState:
    """Simple container for air purifier state returned by ``_fetch_state``.

    Args:
        active: 1 if active, 0 if inactive.
        current_state: One of ``AirPurifierCurrentState`` values.
        target_state: One of ``AirPurifierTargetState`` values.
        rotation_speed: Fan speed percentage (0-100).
    """

    __slots__ = ("active", "current_state", "rotation_speed", "target_state")

    def __init__(
        self,
        *,
        active: int,
        current_state: int,
        target_state: int,
        rotation_speed: float = 0,
    ) -> None:
        self.active = active
        self.current_state = current_state
        self.target_state = target_state
        self.rotation_speed = rotation_speed
