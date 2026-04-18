"""Tests for GoveeLight accessory and capability parsing."""

from unittest.mock import AsyncMock, MagicMock, patch

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
def mock_driver():
    driver = MagicMock()
    driver.loop.run_in_executor = AsyncMock(return_value=SAMPLE_STATE_RESPONSE)
    return driver


@pytest.fixture
def light(mock_client, mock_driver):
    """GoveeLight with HAP initialisation bypassed."""
    with patch("bifrost.accessories.base.light.Light.__init__", return_value=None):
        instance = GoveeLight(
            mock_driver, "Test Light", client=mock_client, sku="H6076", device_id="AA:BB:CC"
        )
    instance.driver = mock_driver
    instance.display_name = "Test Light"
    instance.char_on = MagicMock()
    instance.char_brightness = MagicMock()
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

    def test_normalises_254_scale_max_to_100(self):
        caps = [{"instance": "brightness", "state": {"value": 254}}]
        _, brightness = _parse_capabilities(caps)
        assert brightness == 100

    def test_normalises_254_scale_half_to_50(self):
        caps = [{"instance": "brightness", "state": {"value": 127}}]
        _, brightness = _parse_capabilities(caps)
        assert brightness == 50

    def test_does_not_normalise_values_within_0_to_100(self):
        caps = [{"instance": "brightness", "state": {"value": 75}}]
        _, brightness = _parse_capabilities(caps)
        assert brightness == 75

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
    def test_set_on_calls_turn_on(self, light, mock_client, mock_driver):
        light._set_on(True)
        mock_driver.add_job.assert_called_once_with(mock_client.turn_on_device, "H6076", "AA:BB:CC")

    def test_set_on_calls_turn_off(self, light, mock_client, mock_driver):
        light._set_on(False)
        mock_driver.add_job.assert_called_once_with(
            mock_client.turn_off_device, "H6076", "AA:BB:CC"
        )

    def test_set_brightness(self, light, mock_client, mock_driver):
        light._set_brightness(60)
        mock_driver.add_job.assert_called_once_with(
            mock_client.set_device_brightness, "H6076", "AA:BB:CC", 60
        )


class TestGoveeLightFetchState:
    async def test_returns_parsed_state(self, light, mock_driver):
        on, brightness = await light._fetch_state()
        assert on is True
        assert brightness == 75

    async def test_calls_api_with_correct_ids(self, light, mock_driver):
        await light._fetch_state()
        mock_driver.loop.run_in_executor.assert_called_once()


# ── discover_lights ───────────────────────────────────────────────────────────


class TestDiscoverLights:
    def test_creates_one_light_per_device(self, mock_client):
        mock_client.get_lights.return_value = [
            {"deviceName": "Bedroom", "sku": "H6076", "device": "AA:BB"},
            {"deviceName": "Kitchen", "sku": "H605C", "device": "CC:DD"},
        ]
        with patch("bifrost.accessories.base.light.Light.__init__", return_value=None):
            lights = discover_lights(mock_client, MagicMock())
        assert len(lights) == 2

    def test_maps_device_fields_correctly(self, mock_client):
        mock_client.get_lights.return_value = [
            {"deviceName": "Bedroom", "sku": "H6076", "device": "AA:BB"},
        ]
        with patch("bifrost.accessories.base.light.Light.__init__", return_value=None):
            lights = discover_lights(mock_client, MagicMock())
        assert lights[0]._sku == "H6076"
        assert lights[0]._device_id == "AA:BB"

    def test_empty_account_returns_empty_list(self, mock_client):
        mock_client.get_lights.return_value = []
        with patch("bifrost.accessories.base.light.Light.__init__", return_value=None):
            lights = discover_lights(mock_client, MagicMock())
        assert lights == []
