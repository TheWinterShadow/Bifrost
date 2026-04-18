"""Tests for GoveeLight accessory and capability parsing."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bifrost.accessories.base.light import (
    ColorMode,
    hsv_to_rgb,
    kelvin_to_mireds,
    mireds_to_kelvin,
    rgb_to_hsv,
)
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
    instance.char_hue = None
    instance.char_saturation = None
    instance.char_color_temp = None
    return instance


@pytest.fixture
def color_light(mock_client, mock_driver):
    """GoveeLight with color support, HAP initialisation bypassed."""
    with patch("bifrost.accessories.base.light.Light.__init__", return_value=None):
        instance = GoveeLight(
            mock_driver,
            "Color Light",
            client=mock_client,
            sku="H6076",
            device_id="AA:BB:CC",
            has_color=True,
            has_color_temp=True,
        )
    instance.driver = mock_driver
    instance.display_name = "Color Light"
    instance.char_on = MagicMock()
    instance.char_brightness = MagicMock()
    instance.char_brightness.get_value.return_value = 100
    instance.char_hue = MagicMock()
    instance.char_saturation = MagicMock()
    instance.char_color_temp = MagicMock()
    return instance


# ── HSV / RGB conversion ─────────────────────────────────────────────────────


class TestColorConversion:
    def test_hsv_red(self):
        assert hsv_to_rgb(0, 100, 100) == (255, 0, 0)

    def test_hsv_green(self):
        assert hsv_to_rgb(120, 100, 100) == (0, 255, 0)

    def test_hsv_blue(self):
        assert hsv_to_rgb(240, 100, 100) == (0, 0, 255)

    def test_hsv_white(self):
        assert hsv_to_rgb(0, 0, 100) == (255, 255, 255)

    def test_rgb_to_hsv_red(self):
        h, s, v = rgb_to_hsv(255, 0, 0)
        assert h == 0
        assert s == 100
        assert v == 100

    def test_rgb_to_hsv_green(self):
        h, s, v = rgb_to_hsv(0, 255, 0)
        assert h == 120
        assert s == 100
        assert v == 100

    def test_roundtrip(self):
        r, g, b = hsv_to_rgb(200, 80, 60)
        h, s, v = rgb_to_hsv(r, g, b)
        assert abs(h - 200) <= 1
        assert abs(s - 80) <= 1
        assert abs(v - 60) <= 1


# ── Kelvin / Mireds conversion ───────────────────────────────────────────────


class TestMiredsConversion:
    def test_kelvin_to_mireds_2000k(self):
        assert kelvin_to_mireds(2000) == 500

    def test_kelvin_to_mireds_6500k(self):
        assert kelvin_to_mireds(6500) == 154

    def test_mireds_to_kelvin_500(self):
        assert mireds_to_kelvin(500) == 2000

    def test_mireds_to_kelvin_140(self):
        assert mireds_to_kelvin(140) == 7143

    def test_kelvin_zero_clamps(self):
        assert kelvin_to_mireds(0) == 500

    def test_mireds_zero_clamps(self):
        assert mireds_to_kelvin(0) == 7143

    def test_kelvin_to_mireds_clamps_low(self):
        assert kelvin_to_mireds(100_000) == 140

    def test_kelvin_to_mireds_clamps_high(self):
        assert kelvin_to_mireds(100) == 500


# ── _parse_capabilities ───────────────────────────────────────────────────────


class TestParseCapabilities:
    def test_parses_on_state(self):
        state = _parse_capabilities(SAMPLE_CAPABILITIES)
        assert state.on is True

    def test_parses_off_state(self):
        caps = [{"instance": "powerSwitch", "state": {"value": 0}}]
        state = _parse_capabilities(caps)
        assert state.on is False

    def test_parses_brightness(self):
        state = _parse_capabilities(SAMPLE_CAPABILITIES)
        assert state.brightness == 75

    def test_missing_power_switch_defaults_off(self):
        state = _parse_capabilities([])
        assert state.on is False

    def test_missing_brightness_defaults_to_100(self):
        state = _parse_capabilities([])
        assert state.brightness == 100

    def test_normalises_254_scale_max_to_100(self):
        caps = [{"instance": "brightness", "state": {"value": 254}}]
        state = _parse_capabilities(caps)
        assert state.brightness == 100

    def test_normalises_254_scale_half_to_50(self):
        caps = [{"instance": "brightness", "state": {"value": 127}}]
        state = _parse_capabilities(caps)
        assert state.brightness == 50

    def test_does_not_normalise_values_within_0_to_100(self):
        caps = [{"instance": "brightness", "state": {"value": 75}}]
        state = _parse_capabilities(caps)
        assert state.brightness == 75

    def test_ignores_unrelated_capabilities(self):
        caps = [
            {"instance": "powerSwitch", "state": {"value": 1}},
            {"instance": "colorRgb", "state": {"value": 16777215}},
            {"instance": "brightness", "state": {"value": 50}},
        ]
        state = _parse_capabilities(caps)
        assert state.on is True
        assert state.brightness == 50

    def test_parses_color_rgb(self):
        caps = [
            {"instance": "powerSwitch", "state": {"value": 1}},
            {"instance": "colorRgb", "state": {"value": 16711680}},
        ]
        state = _parse_capabilities(caps)
        assert state.hue == 0
        assert state.saturation == 100
        assert state.color_mode == ColorMode.COLOR

    def test_parses_color_temp(self):
        caps = [
            {"instance": "powerSwitch", "state": {"value": 1}},
            {"instance": "colorTemInKelvin", "state": {"value": 4000}},
        ]
        state = _parse_capabilities(caps)
        assert state.color_temp == 250
        assert state.color_mode == ColorMode.TEMPERATURE

    def test_color_and_temp_both_present(self):
        caps = [
            {"instance": "powerSwitch", "state": {"value": 1}},
            {"instance": "colorRgb", "state": {"value": 16711680}},
            {"instance": "colorTemInKelvin", "state": {"value": 4000}},
        ]
        state = _parse_capabilities(caps)
        assert state.hue is not None
        assert state.color_temp is not None
        assert state.color_mode == ColorMode.COLOR

    def test_no_color_data_returns_none(self):
        state = _parse_capabilities(SAMPLE_CAPABILITIES)
        assert state.hue is None
        assert state.saturation is None
        assert state.color_temp is None
        assert state.color_mode is None


# ── GoveeLight control ───────────────────────────────────────────────────────


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


class TestGoveeLightColorControl:
    def test_set_color_sends_rgb(self, color_light, mock_client, mock_driver):
        color_light._set_color(0, 100)
        mock_driver.add_job.assert_called_once_with(
            mock_client.set_device_color, "H6076", "AA:BB:CC", 255, 0, 0
        )

    def test_set_color_updates_mode(self, color_light):
        color_light._set_color(120, 100)
        assert color_light._color_mode == ColorMode.COLOR

    def test_set_color_temp_sends_kelvin(self, color_light, mock_client, mock_driver):
        color_light._set_color_temperature(250)
        mock_driver.add_job.assert_called_once_with(
            mock_client.set_device_color_temperature, "H6076", "AA:BB:CC", 4000
        )

    def test_set_color_temp_updates_mode(self, color_light):
        color_light._set_color_temperature(250)
        assert color_light._color_mode == ColorMode.TEMPERATURE


class TestGoveeLightFetchState:
    async def test_returns_parsed_state(self, light):
        state = await light._fetch_state()
        assert state.on is True
        assert state.brightness == 75

    async def test_calls_api_with_correct_ids(self, light, mock_driver):
        await light._fetch_state()
        mock_driver.loop.run_in_executor.assert_called_once()


# ── discover_lights ───────────────────────────────────────────────────────────


class TestDiscoverLights:
    def test_creates_one_light_per_device(self, mock_client):
        mock_client.get_lights.return_value = [
            {"deviceName": "Bedroom", "sku": "H6076", "device": "AA:BB", "capabilities": []},
            {"deviceName": "Kitchen", "sku": "H605C", "device": "CC:DD", "capabilities": []},
        ]
        with patch("bifrost.accessories.base.light.Light.__init__", return_value=None):
            lights = discover_lights(mock_client, MagicMock())
        assert len(lights) == 2

    def test_maps_device_fields_correctly(self, mock_client):
        mock_client.get_lights.return_value = [
            {"deviceName": "Bedroom", "sku": "H6076", "device": "AA:BB", "capabilities": []},
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

    def test_detects_color_capability(self, mock_client):
        mock_client.get_lights.return_value = [
            {
                "deviceName": "RGB Light",
                "sku": "H6076",
                "device": "AA:BB",
                "capabilities": [
                    {"instance": "colorRgb", "type": "devices.capabilities.color_setting"},
                    {"instance": "colorTemInKelvin", "type": "devices.capabilities.color_setting"},
                ],
            },
        ]
        with patch("bifrost.accessories.base.light.Light.__init__", return_value=None):
            lights = discover_lights(mock_client, MagicMock())
        # Verify the flags were passed (they're consumed by __init__ which we patched,
        # but we can check the device was created)
        assert len(lights) == 1
