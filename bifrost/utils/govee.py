"""Govee API client."""

import logging
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)


class GoveeClient:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def _call_api(
        self, endpoint: str, method: str = "GET", data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        url = f"https://openapi.api.govee.com/router/api/v1{endpoint}"
        headers = {
            "Govee-API-Key": self.api_key,
            "Content-Type": "application/json",
        }

        logger.debug("%s %s body=%s", method, endpoint, data)
        t0 = time.monotonic()

        try:
            if method == "GET":
                r = requests.get(url, headers=headers, timeout=10)
            elif method == "POST":
                r = requests.post(url, headers=headers, json=data, timeout=10)
            else:
                raise ValueError(f"Invalid HTTP method: {method}")
        except requests.Timeout:
            logger.error("%s %s timed out after 10s", method, endpoint)
            raise
        except requests.RequestException as exc:
            logger.error("%s %s request failed: %s", method, endpoint, exc)
            raise

        elapsed = (time.monotonic() - t0) * 1000
        logger.debug("%s %s → %d (%.0fms)", method, endpoint, r.status_code, elapsed)

        if not r.ok:
            logger.error("%s %s failed: status=%d body=%s", method, endpoint, r.status_code, r.text)
            r.raise_for_status()

        body = r.json()
        if body.get("code", 200) != 200:
            logger.error(
                "%s %s API error: code=%s msg=%s",
                method,
                endpoint,
                body.get("code"),
                body.get("msg"),
            )

        return body

    def get_lights(self) -> list[dict[str, Any]]:
        logger.debug("Fetching device list")
        devices = self._call_api("/user/devices")["data"]
        lights = [
            d for d in devices if d["sku"] != "BaseGroup" and d["type"] == "devices.types.light"
        ]
        logger.debug("Found %d light(s) out of %d device(s)", len(lights), len(devices))
        return lights

    def turn_on_device(self, device_sku: str, device_id: str) -> dict[str, Any]:
        logger.debug("Turning ON %s / %s", device_sku, device_id)
        result = self._call_api(
            "/device/control",
            method="POST",
            data={
                "requestId": "uuid",
                "payload": {
                    "sku": device_sku,
                    "device": device_id,
                    "capability": {
                        "type": "devices.capabilities.on_off",
                        "instance": "powerSwitch",
                        "value": 1,
                    },
                },
            },
        )
        logger.debug("Turn ON %s / %s result: %s", device_sku, device_id, result.get("msg"))
        return result

    def turn_off_device(self, device_sku: str, device_id: str) -> dict[str, Any]:
        logger.debug("Turning OFF %s / %s", device_sku, device_id)
        result = self._call_api(
            "/device/control",
            method="POST",
            data={
                "requestId": "uuid",
                "payload": {
                    "sku": device_sku,
                    "device": device_id,
                    "capability": {
                        "type": "devices.capabilities.on_off",
                        "instance": "powerSwitch",
                        "value": 0,
                    },
                },
            },
        )
        logger.debug("Turn OFF %s / %s result: %s", device_sku, device_id, result.get("msg"))
        return result

    def get_device_state(self, device_sku: str, device_id: str) -> dict[str, Any]:
        logger.debug("Fetching state for %s / %s", device_sku, device_id)
        return self._call_api(
            "/device/state",
            method="POST",
            data={"requestId": "uuid", "payload": {"sku": device_sku, "device": device_id}},
        )

    def set_device_brightness(
        self, device_sku: str, device_id: str, brightness: int
    ) -> dict[str, Any]:
        logger.debug("Setting brightness %d%% on %s / %s", brightness, device_sku, device_id)
        result = self._call_api(
            "/device/control",
            method="POST",
            data={
                "requestId": "1",
                "payload": {
                    "sku": device_sku,
                    "device": device_id,
                    "capability": {
                        "type": "devices.capabilities.range",
                        "instance": "brightness",
                        "value": brightness,
                    },
                },
            },
        )
        logger.debug("Set brightness %s / %s result: %s", device_sku, device_id, result.get("msg"))
        return result
