"""Smoke tests for bridge construction and accessory discovery."""

from unittest.mock import MagicMock, patch

import pytest

from bifrost.bridge import build_bridge


@pytest.fixture
def mock_driver():
    driver = MagicMock()
    driver.add_job = MagicMock()
    return driver


@pytest.fixture
def _patch_bridge():
    """Patch Bridge.__init__ to avoid HAP loader dependency."""
    with patch("bifrost.bridge.Bridge.__init__", return_value=None) as mock_init:
        yield mock_init


def _make_bridge_stub():
    """Create a minimal Bridge-like object with an accessories dict."""
    from pyhap.accessory import Bridge

    bridge = Bridge.__new__(Bridge)
    bridge.display_name = "Bifrost"
    bridge.accessories = {}
    bridge.aid = 1
    bridge._next_id = 2
    return bridge


class TestBuildBridge:
    @patch("bifrost.bridge.discover_air_purifiers", return_value=[])
    @patch("bifrost.bridge.discover_lights", return_value=[])
    @patch("bifrost.bridge.GoveeClient")
    @patch.dict("os.environ", {"GOVEE_API_KEY": "fake-key"})
    @patch("bifrost.bridge.Bridge")
    def test_returns_bridge_with_no_devices(
        self, mock_bridge_cls, _client_cls, _lights, _purifiers, mock_driver
    ):
        bridge = _make_bridge_stub()
        mock_bridge_cls.return_value = bridge

        result = build_bridge(mock_driver)
        assert result is bridge
        assert len(result.accessories) == 0

    @patch("bifrost.bridge.discover_air_purifiers", return_value=[])
    @patch("bifrost.bridge.discover_lights")
    @patch("bifrost.bridge.GoveeClient")
    @patch.dict("os.environ", {"GOVEE_API_KEY": "fake-key"})
    @patch("bifrost.bridge.Bridge")
    def test_adds_lights_to_bridge(
        self, mock_bridge_cls, _client_cls, mock_lights, _purifiers, mock_driver
    ):
        bridge = _make_bridge_stub()
        mock_bridge_cls.return_value = bridge
        light = MagicMock()
        light.aid = None
        mock_lights.return_value = [light]

        result = build_bridge(mock_driver)
        assert len(result.accessories) == 1

    @patch("bifrost.bridge.discover_air_purifiers")
    @patch("bifrost.bridge.discover_lights", return_value=[])
    @patch("bifrost.bridge.GoveeClient")
    @patch.dict("os.environ", {"GOVEE_API_KEY": "fake-key"})
    @patch("bifrost.bridge.Bridge")
    def test_adds_air_purifiers_to_bridge(
        self, mock_bridge_cls, _client_cls, _lights, mock_purifiers, mock_driver
    ):
        bridge = _make_bridge_stub()
        mock_bridge_cls.return_value = bridge
        purifier = MagicMock()
        purifier.aid = None
        mock_purifiers.return_value = [purifier]

        result = build_bridge(mock_driver)
        assert len(result.accessories) == 1

    @patch("bifrost.bridge.discover_air_purifiers")
    @patch("bifrost.bridge.discover_lights")
    @patch("bifrost.bridge.GoveeClient")
    @patch.dict("os.environ", {"GOVEE_API_KEY": "fake-key"})
    @patch("bifrost.bridge.Bridge")
    def test_adds_mixed_accessories(
        self, mock_bridge_cls, _client_cls, mock_lights, mock_purifiers, mock_driver
    ):
        bridge = _make_bridge_stub()
        mock_bridge_cls.return_value = bridge
        light = MagicMock()
        light.aid = None
        purifier = MagicMock()
        purifier.aid = None
        mock_lights.return_value = [light]
        mock_purifiers.return_value = [purifier]

        result = build_bridge(mock_driver)
        assert len(result.accessories) == 2

    @patch("bifrost.bridge.discover_air_purifiers")
    @patch("bifrost.bridge.discover_lights")
    @patch.dict("os.environ", {}, clear=True)
    @patch("bifrost.bridge.Bridge")
    def test_missing_api_key_returns_empty_bridge(
        self, mock_bridge_cls, _lights, _purifiers, mock_driver
    ):
        bridge = _make_bridge_stub()
        mock_bridge_cls.return_value = bridge

        result = build_bridge(mock_driver)
        assert len(result.accessories) == 0
        _lights.assert_not_called()
        _purifiers.assert_not_called()

    @patch("bifrost.bridge.discover_air_purifiers", return_value=[])
    @patch("bifrost.bridge.discover_lights", return_value=[])
    @patch("bifrost.bridge.GoveeClient")
    @patch.dict("os.environ", {"GOVEE_API_KEY": "fake-key"})
    @patch("bifrost.bridge.Bridge")
    def test_passes_api_key_to_client(
        self, mock_bridge_cls, mock_client_cls, _lights, _purifiers, mock_driver
    ):
        mock_bridge_cls.return_value = _make_bridge_stub()
        build_bridge(mock_driver)
        mock_client_cls.assert_called_once_with("fake-key")

    @patch("bifrost.bridge.discover_air_purifiers", return_value=[])
    @patch("bifrost.bridge.discover_lights", return_value=[])
    @patch("bifrost.bridge.GoveeClient")
    @patch.dict("os.environ", {"GOVEE_API_KEY": "fake-key"})
    @patch("bifrost.bridge.Bridge")
    def test_passes_client_and_driver_to_discover(
        self, mock_bridge_cls, mock_client_cls, mock_lights, mock_purifiers, mock_driver
    ):
        mock_bridge_cls.return_value = _make_bridge_stub()
        client_instance = mock_client_cls.return_value
        build_bridge(mock_driver)
        mock_lights.assert_called_once_with(client_instance, mock_driver)
        mock_purifiers.assert_called_once_with(client_instance, mock_driver)
