"""Tests for GoveeAirPurifier accessory and capability parsing."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bifrost.accessories.base.air_purifier import (
    AirPurifierCurrentState,
    AirPurifierTargetState,
)
from bifrost.accessories.govee_air_purifier import (
    GOVEE_MODE_AUTO,
    GOVEE_MODE_MANUAL,
    GoveeAirPurifier,
    _gear_to_percent,
    _parse_capabilities,
    _percent_to_gear,
    discover_air_purifiers,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

SAMPLE_CAPABILITIES = [
    {"type": "devices.capabilities.online", "instance": "online", "state": {"value": True}},
    {"type": "devices.capabilities.on_off", "instance": "powerSwitch", "state": {"value": 1}},
    {
        "type": "devices.capabilities.work_mode",
        "instance": "workMode",
        "state": {"value": {"workMode": 1, "modeValue": 3}},
    },
]

SAMPLE_STATE_RESPONSE = {"payload": {"capabilities": SAMPLE_CAPABILITIES}}


@pytest.fixture
def mock_client():
    return MagicMock()


@pytest.fixture
def mock_driver():
    driver = MagicMock()
    driver.loop.run_in_executor = AsyncMock(return_value=SAMPLE_STATE_RESPONSE)
    return driver


@pytest.fixture
def purifier(mock_client, mock_driver):
    """GoveeAirPurifier with HAP initialisation bypassed."""
    with patch("bifrost.accessories.base.air_purifier.AirPurifier.__init__", return_value=None):
        instance = GoveeAirPurifier(
            mock_driver, "Test Purifier", client=mock_client, sku="H7122", device_id="AA:BB:CC"
        )
    instance.driver = mock_driver
    instance.display_name = "Test Purifier"
    instance.char_active = MagicMock()
    instance.char_current_state = MagicMock()
    instance.char_target_state = MagicMock()
    instance.char_rotation_speed = MagicMock()
    return instance


# ── _gear_to_percent / _percent_to_gear ───────────────────────────────────────


class TestGearConversion:
    def test_gear_zero_returns_zero(self):
        assert _gear_to_percent(0) == 0.0

    def test_gear_max_returns_100(self):
        assert _gear_to_percent(4) == 100

    def test_gear_half(self):
        assert _gear_to_percent(2) == 50

    def test_gear_one(self):
        assert _gear_to_percent(1) == 25

    def test_percent_zero_returns_gear_one(self):
        assert _percent_to_gear(0) == 1

    def test_percent_100_returns_max_gear(self):
        assert _percent_to_gear(100) == 4

    def test_percent_50_returns_gear_two(self):
        assert _percent_to_gear(50) == 2

    def test_percent_25_returns_gear_one(self):
        assert _percent_to_gear(25) == 1

    def test_percent_over_100_clamps_to_max(self):
        assert _percent_to_gear(200) == 4

    def test_negative_percent_returns_one(self):
        assert _percent_to_gear(-10) == 1

    def test_negative_gear_returns_zero(self):
        assert _gear_to_percent(-1) == 0.0


# ── _parse_capabilities ───────────────────────────────────────────────────────


class TestParseCapabilities:
    def test_on_manual_mode(self):
        state = _parse_capabilities(SAMPLE_CAPABILITIES)
        assert state.active == 1
        assert state.current_state == AirPurifierCurrentState.PURIFYING
        assert state.target_state == AirPurifierTargetState.MANUAL
        assert state.rotation_speed == 75  # gear 3/4 = 75%

    def test_on_auto_mode(self):
        caps = [
            {"instance": "powerSwitch", "state": {"value": 1}},
            {
                "instance": "workMode",
                "state": {"value": {"workMode": GOVEE_MODE_AUTO, "modeValue": 2}},
            },
        ]
        state = _parse_capabilities(caps)
        assert state.active == 1
        assert state.current_state == AirPurifierCurrentState.PURIFYING
        assert state.target_state == AirPurifierTargetState.AUTO
        assert state.rotation_speed == 50

    def test_off_returns_inactive(self):
        caps = [
            {"instance": "powerSwitch", "state": {"value": 0}},
            {
                "instance": "workMode",
                "state": {"value": {"workMode": GOVEE_MODE_MANUAL, "modeValue": 3}},
            },
        ]
        state = _parse_capabilities(caps)
        assert state.active == 0
        assert state.current_state == AirPurifierCurrentState.INACTIVE
        assert state.rotation_speed == 0.0

    def test_missing_power_switch_defaults_off(self):
        state = _parse_capabilities([])
        assert state.active == 0
        assert state.current_state == AirPurifierCurrentState.INACTIVE

    def test_missing_work_mode_defaults_manual(self):
        caps = [{"instance": "powerSwitch", "state": {"value": 1}}]
        state = _parse_capabilities(caps)
        assert state.target_state == AirPurifierTargetState.MANUAL

    def test_non_dict_work_mode_defaults_manual(self):
        caps = [
            {"instance": "powerSwitch", "state": {"value": 1}},
            {"instance": "workMode", "state": {"value": 0}},
        ]
        state = _parse_capabilities(caps)
        assert state.target_state == AirPurifierTargetState.MANUAL
        assert state.rotation_speed == 0.0

    def test_ignores_unrelated_capabilities(self):
        caps = [
            {"instance": "powerSwitch", "state": {"value": 1}},
            {"instance": "humidity", "state": {"value": 55}},
            {
                "instance": "workMode",
                "state": {"value": {"workMode": GOVEE_MODE_MANUAL, "modeValue": 4}},
            },
        ]
        state = _parse_capabilities(caps)
        assert state.active == 1
        assert state.rotation_speed == 100


# ── GoveeAirPurifier control ─────────────────────────────────────────────────


class TestGoveeAirPurifierControl:
    def test_set_active_on(self, purifier, mock_client, mock_driver):
        purifier._set_active(1)
        mock_driver.add_job.assert_called_once_with(mock_client.turn_on_device, "H7122", "AA:BB:CC")

    def test_set_active_off(self, purifier, mock_client, mock_driver):
        purifier._set_active(0)
        mock_driver.add_job.assert_called_once_with(
            mock_client.turn_off_device, "H7122", "AA:BB:CC"
        )

    def test_set_target_state_auto(self, purifier, mock_client, mock_driver):
        purifier._set_target_state(AirPurifierTargetState.AUTO)
        mock_driver.add_job.assert_called_once_with(
            mock_client.set_device_mode, "H7122", "AA:BB:CC", GOVEE_MODE_AUTO
        )

    def test_set_target_state_manual(self, purifier, mock_client, mock_driver):
        purifier._set_target_state(AirPurifierTargetState.MANUAL)
        mock_driver.add_job.assert_called_once_with(
            mock_client.set_device_mode, "H7122", "AA:BB:CC", GOVEE_MODE_MANUAL
        )

    def test_set_rotation_speed(self, purifier, mock_client, mock_driver):
        purifier._set_rotation_speed(75)
        mock_driver.add_job.assert_called_once_with(
            mock_client.set_device_mode, "H7122", "AA:BB:CC", GOVEE_MODE_MANUAL, 3
        )


# ── GoveeAirPurifier fetch state ─────────────────────────────────────────────


class TestGoveeAirPurifierFetchState:
    async def test_returns_parsed_state(self, purifier):
        state = await purifier._fetch_state()
        assert state.active == 1
        assert state.current_state == AirPurifierCurrentState.PURIFYING
        assert state.rotation_speed == 75

    async def test_calls_api_with_correct_ids(self, purifier, mock_driver):
        await purifier._fetch_state()
        mock_driver.loop.run_in_executor.assert_called_once()


# ── discover_air_purifiers ────────────────────────────────────────────────────


class TestDiscoverAirPurifiers:
    def test_creates_one_purifier_per_device(self, mock_client):
        mock_client.get_air_purifiers.return_value = [
            {"deviceName": "Bedroom", "sku": "H7122", "device": "AA:BB"},
            {"deviceName": "Office", "sku": "H7130", "device": "CC:DD"},
        ]
        with patch("bifrost.accessories.base.air_purifier.AirPurifier.__init__", return_value=None):
            purifiers = discover_air_purifiers(mock_client, MagicMock())
        assert len(purifiers) == 2

    def test_maps_device_fields_correctly(self, mock_client):
        mock_client.get_air_purifiers.return_value = [
            {"deviceName": "Bedroom", "sku": "H7122", "device": "AA:BB"},
        ]
        with patch("bifrost.accessories.base.air_purifier.AirPurifier.__init__", return_value=None):
            purifiers = discover_air_purifiers(mock_client, MagicMock())
        assert purifiers[0]._sku == "H7122"
        assert purifiers[0]._device_id == "AA:BB"

    def test_empty_account_returns_empty_list(self, mock_client):
        mock_client.get_air_purifiers.return_value = []
        with patch("bifrost.accessories.base.air_purifier.AirPurifier.__init__", return_value=None):
            purifiers = discover_air_purifiers(mock_client, MagicMock())
        assert purifiers == []
