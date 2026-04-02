"""Tests for GoveeLight accessory and capability parsing."""

from unittest.mock import MagicMock, patch

import pytest

from bifrost.accessories.govee_light import GoveeLight, _parse_capabilities, discover_lights

# ── Fixtures ──────────────────────────────────────────────────────────────────

SAMPLE_CAPABILITIES = [
    {"type": "devices.capabilities.online", "instance": "online", "state": {"value": True}},
    {"type": "devices.capabilities.on_off", "instance": "powerSwitch", "state": {"value": 1}},
    {"type": "devices.capabilities.range", "instance": "brightness", "state": {"value": 75}},
]

SAMPLE_STATE_RESPONSE = {"payload": {"capabilities": SAMPLE_CAPABILITIES}}


@pytest.fixture
def mock_client():
    return MagicMock()


@pytest.fixture
def light(mock_client):
    """GoveeLight with HAP initialisation bypassed."""
    with patch("bifrost.accessories.light.Light.__init__", return_value=None):
        instance = GoveeLight(
            MagicMock(), "Test Light", client=mock_client, sku="H6076", device_id="AA:BB:CC"
        )
    return instance


# ── _parse_capabilities ───────────────────────────────────────────────────────


class TestParseCapabilities:
    def test_parses_on_state(self):
        on, _ = _parse_capabilities(SAMPLE_CAPABILITIES)
        assert on is True

    def test_parses_off_state(self):
        caps = [{"instance": "powerSwitch", "state": {"value": 0}}]
        on, _ = _parse_capabilities(caps)
        assert on is False

    def test_parses_brightness(self):
        _, brightness = _parse_capabilities(SAMPLE_CAPABILITIES)
        assert brightness == 75

    def test_missing_power_switch_defaults_off(self):
        on, _ = _parse_capabilities([])
        assert on is False

    def test_missing_brightness_defaults_to_100(self):
        _, brightness = _parse_capabilities([])
        assert brightness == 100

    def test_ignores_unrelated_capabilities(self):
        caps = [
            {"instance": "powerSwitch", "state": {"value": 1}},
            {"instance": "colorRgb", "state": {"value": 16777215}},
            {"instance": "brightness", "state": {"value": 50}},
        ]
        on, brightness = _parse_capabilities(caps)
        assert on is True
        assert brightness == 50


# ── GoveeLight ────────────────────────────────────────────────────────────────


class TestGoveeLightControl:
    def test_set_on_calls_turn_on(self, light, mock_client):
        light._set_on(True)
        mock_client.turn_on_device.assert_called_once_with("H6076", "AA:BB:CC")
        mock_client.turn_off_device.assert_not_called()

    def test_set_on_calls_turn_off(self, light, mock_client):
        light._set_on(False)
        mock_client.turn_off_device.assert_called_once_with("H6076", "AA:BB:CC")
        mock_client.turn_on_device.assert_not_called()

    def test_set_brightness(self, light, mock_client):
        light._set_brightness(60)
        mock_client.set_device_brightness.assert_called_once_with("H6076", "AA:BB:CC", 60)


class TestGoveeLightFetchState:
    async def test_returns_parsed_state(self, light, mock_client):
        mock_client.get_device_state.return_value = SAMPLE_STATE_RESPONSE
        on, brightness = await light._fetch_state()
        assert on is True
        assert brightness == 75

    async def test_calls_api_with_correct_ids(self, light, mock_client):
        mock_client.get_device_state.return_value = SAMPLE_STATE_RESPONSE
        await light._fetch_state()
        mock_client.get_device_state.assert_called_once_with("H6076", "AA:BB:CC")


# ── discover_lights ───────────────────────────────────────────────────────────


class TestDiscoverLights:
    def test_creates_one_light_per_device(self, mock_client):
        mock_client.get_lights.return_value = [
            {"deviceName": "Bedroom", "sku": "H6076", "device": "AA:BB"},
            {"deviceName": "Kitchen", "sku": "H605C", "device": "CC:DD"},
        ]
        with patch("bifrost.accessories.light.Light.__init__", return_value=None):
            lights = discover_lights(mock_client, MagicMock())
        assert len(lights) == 2

    def test_maps_device_fields_correctly(self, mock_client):
        mock_client.get_lights.return_value = [
            {"deviceName": "Bedroom", "sku": "H6076", "device": "AA:BB"},
        ]
        with patch("bifrost.accessories.light.Light.__init__", return_value=None):
            lights = discover_lights(mock_client, MagicMock())
        assert lights[0]._sku == "H6076"
        assert lights[0]._device_id == "AA:BB"

    def test_empty_account_returns_empty_list(self, mock_client):
        mock_client.get_lights.return_value = []
        with patch("bifrost.accessories.light.Light.__init__", return_value=None):
            lights = discover_lights(mock_client, MagicMock())
        assert lights == []
