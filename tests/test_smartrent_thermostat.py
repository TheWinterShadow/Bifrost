"""Tests for SmartRent thermostat accessory."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bifrost.accessories.base.thermostat import HeatingCoolingState, TemperatureUnit
from bifrost.accessories.smartrent_thermostat import (
    SmartRentThermostat,
    c_to_f,
    discover_thermostats,
    f_to_c,
    hap_target_to_sr_mode,
    sr_mode_to_hap_target,
    sr_opstate_to_hap_current,
    target_temp_for_mode,
)

# ── Temperature conversion ───────────────────────────────────────────────────


class TestFToC:
    def test_freezing(self) -> None:
        assert f_to_c(32) == 0.0

    def test_boiling(self) -> None:
        assert f_to_c(212) == 100.0

    def test_room_temp(self) -> None:
        assert f_to_c(69) == 20.6

    def test_negative(self) -> None:
        assert f_to_c(-40) == -40.0


class TestCToF:
    def test_freezing(self) -> None:
        assert c_to_f(0.0) == 32

    def test_boiling(self) -> None:
        assert c_to_f(100.0) == 212

    def test_room_temp(self) -> None:
        assert c_to_f(20.6) == 69

    def test_negative(self) -> None:
        assert c_to_f(-40.0) == -40


# ── Mode mapping ─────────────────────────────────────────────────────────────


class TestSrModeToHapTarget:
    def test_off(self) -> None:
        assert sr_mode_to_hap_target("off") == HeatingCoolingState.OFF

    def test_heat(self) -> None:
        assert sr_mode_to_hap_target("heat") == HeatingCoolingState.HEAT

    def test_aux_heat(self) -> None:
        assert sr_mode_to_hap_target("aux_heat") == HeatingCoolingState.HEAT

    def test_cool(self) -> None:
        assert sr_mode_to_hap_target("cool") == HeatingCoolingState.COOL

    def test_auto(self) -> None:
        assert sr_mode_to_hap_target("auto") == HeatingCoolingState.AUTO

    def test_none_defaults_off(self) -> None:
        assert sr_mode_to_hap_target(None) == HeatingCoolingState.OFF

    def test_unknown_defaults_off(self) -> None:
        assert sr_mode_to_hap_target("turbo") == HeatingCoolingState.OFF


class TestHapTargetToSrMode:
    def test_off(self) -> None:
        assert hap_target_to_sr_mode(HeatingCoolingState.OFF) == "off"

    def test_heat(self) -> None:
        assert hap_target_to_sr_mode(HeatingCoolingState.HEAT) == "heat"

    def test_cool(self) -> None:
        assert hap_target_to_sr_mode(HeatingCoolingState.COOL) == "cool"

    def test_auto(self) -> None:
        assert hap_target_to_sr_mode(HeatingCoolingState.AUTO) == "auto"

    def test_unknown_defaults_off(self) -> None:
        assert hap_target_to_sr_mode(99) == "off"


class TestSrOpstateToHapCurrent:
    def test_off(self) -> None:
        assert sr_opstate_to_hap_current("off") == HeatingCoolingState.OFF

    def test_idle(self) -> None:
        assert sr_opstate_to_hap_current("idle") == HeatingCoolingState.OFF

    def test_heating(self) -> None:
        assert sr_opstate_to_hap_current("heating") == HeatingCoolingState.HEAT

    def test_cooling(self) -> None:
        assert sr_opstate_to_hap_current("cooling") == HeatingCoolingState.COOL

    def test_none_defaults_off(self) -> None:
        assert sr_opstate_to_hap_current(None) == HeatingCoolingState.OFF


# ── Target temp selection ────────────────────────────────────────────────────


class TestTargetTempForMode:
    def test_heat_mode(self) -> None:
        assert target_temp_for_mode("heat", 69, 75) == f_to_c(69)

    def test_aux_heat_mode(self) -> None:
        assert target_temp_for_mode("aux_heat", 69, 75) == f_to_c(69)

    def test_cool_mode(self) -> None:
        assert target_temp_for_mode("cool", 69, 75) == f_to_c(75)

    def test_auto_mode_midpoint(self) -> None:
        expected = round((f_to_c(68) + f_to_c(72)) / 2, 1)
        assert target_temp_for_mode("auto", 68, 72) == expected

    def test_off_mode_uses_heat(self) -> None:
        assert target_temp_for_mode("off", 69, 75) == f_to_c(69)

    def test_none_setpoints_default(self) -> None:
        assert target_temp_for_mode("heat", None, None) == 20.0


# ── SmartRentThermostat accessory ────────────────────────────────────────────


@pytest.fixture
def mock_driver() -> MagicMock:
    driver = MagicMock()
    driver.loop = MagicMock()
    return driver


@pytest.fixture
def mock_sr_device() -> MagicMock:
    device = MagicMock()
    device._device_id = 4082853
    device.get_name.return_value = "Thermostat"
    device.get_mode.return_value = "cool"
    device.get_fan_mode.return_value = "on"
    device.get_operating_state.return_value = "off"
    device.get_cooling_setpoint.return_value = 69
    device.get_heating_setpoint.return_value = 69
    device.get_current_humidity.return_value = 56
    device.get_current_temp.return_value = 69
    device._async_fetch_state = AsyncMock()
    device.async_set_mode = AsyncMock()
    device.async_set_heating_setpoint = AsyncMock()
    device.async_set_cooling_setpoint = AsyncMock()
    return device


@pytest.fixture
def thermostat(mock_driver: MagicMock, mock_sr_device: MagicMock) -> SmartRentThermostat:
    with patch("bifrost.accessories.base.thermostat.Thermostat.__init__", return_value=None):
        instance = SmartRentThermostat(mock_driver, "Thermostat", device=mock_sr_device)
    instance.driver = mock_driver
    instance.display_name = "Thermostat"
    instance.char_current_heating_cooling = MagicMock()
    instance.char_target_heating_cooling = MagicMock()
    instance.char_current_temp = MagicMock()
    instance.char_target_temp = MagicMock()
    instance.char_display_units = MagicMock()
    return instance


class TestSetTargetHeatingCoolingState:
    def test_sets_mode_cool(self, thermostat: SmartRentThermostat) -> None:
        thermostat._set_target_heating_cooling_state(HeatingCoolingState.COOL)
        thermostat.char_target_heating_cooling.set_value.assert_called_with(
            HeatingCoolingState.COOL
        )

    def test_sets_mode_off(self, thermostat: SmartRentThermostat) -> None:
        thermostat._set_target_heating_cooling_state(HeatingCoolingState.OFF)
        thermostat.char_target_heating_cooling.set_value.assert_called_with(HeatingCoolingState.OFF)


class TestSetTargetTemperature:
    def test_cool_mode_sets_cooling_setpoint(
        self, thermostat: SmartRentThermostat, mock_sr_device: MagicMock
    ) -> None:
        mock_sr_device.get_mode.return_value = "cool"
        thermostat._set_target_temperature(20.0)
        thermostat.char_target_temp.set_value.assert_called_with(20.0)

    def test_heat_mode_sets_heating_setpoint(
        self, thermostat: SmartRentThermostat, mock_sr_device: MagicMock
    ) -> None:
        mock_sr_device.get_mode.return_value = "heat"
        thermostat._set_target_temperature(22.0)
        thermostat.char_target_temp.set_value.assert_called_with(22.0)

    def test_auto_mode_sets_both(
        self, thermostat: SmartRentThermostat, mock_sr_device: MagicMock
    ) -> None:
        mock_sr_device.get_mode.return_value = "auto"
        thermostat._set_target_temperature(21.0)
        thermostat.char_target_temp.set_value.assert_called_with(21.0)


class TestSetTemperatureDisplayUnits:
    def test_sets_value(self, thermostat: SmartRentThermostat) -> None:
        thermostat._set_temperature_display_units(TemperatureUnit.CELSIUS)
        thermostat.char_display_units.set_value.assert_called_with(TemperatureUnit.CELSIUS)


class TestFetchState:
    @pytest.mark.asyncio
    async def test_returns_thermostat_state(
        self, thermostat: SmartRentThermostat, mock_sr_device: MagicMock
    ) -> None:
        state = await thermostat._fetch_state()

        mock_sr_device._async_fetch_state.assert_awaited_once()
        assert state.current_mode == HeatingCoolingState.OFF
        assert state.target_mode == HeatingCoolingState.COOL
        assert state.current_temp == f_to_c(69)
        assert state.target_temp == f_to_c(69)
        assert state.display_units == TemperatureUnit.FAHRENHEIT

    @pytest.mark.asyncio
    async def test_fetch_state_none_temp_defaults(
        self, thermostat: SmartRentThermostat, mock_sr_device: MagicMock
    ) -> None:
        mock_sr_device.get_current_temp.return_value = None
        state = await thermostat._fetch_state()
        assert state.current_temp == f_to_c(68)


# ── Discovery ────────────────────────────────────────────────────────────────


class TestDiscoverThermostats:
    def test_creates_accessories(self, mock_driver: MagicMock) -> None:
        device = MagicMock()
        device._device_id = 123
        device.get_name.return_value = "Living Room"

        with patch("bifrost.accessories.base.thermostat.Thermostat.__init__", return_value=None):
            result = discover_thermostats([device], mock_driver)

        assert len(result) == 1
        assert result[0]._device == device

    def test_empty_list(self, mock_driver: MagicMock) -> None:
        result = discover_thermostats([], mock_driver)
        assert result == []

    def test_fallback_name(self, mock_driver: MagicMock) -> None:
        device = MagicMock()
        device._device_id = 456
        device.get_name.return_value = None

        with patch(
            "bifrost.accessories.base.thermostat.Thermostat.__init__", return_value=None
        ) as mock_init:
            result = discover_thermostats([device], mock_driver)

        mock_init.assert_called_once_with(mock_driver, "Thermostat 456")
        assert result[0]._device == device
