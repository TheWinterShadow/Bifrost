from typing import Any

import requests


class GoveeClient:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def _call_api(
        self, endpoint: str, method: str = "GET", data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        headers = {
            "Govee-API-Key": self.api_key,
            "Content-Type": "application/json",
        }
        url = f"https://openapi.api.govee.com/router/api/v1{endpoint}"
        if method == "GET":
            r = requests.get(url, headers=headers)
        elif method == "POST":
            r = requests.post(url, headers=headers, json=data)
        else:
            raise ValueError("Invalid HTTP method")
        return r.json()

    def get_lights(self) -> list[dict[str, Any]]:
        devices = self._call_api("/user/devices")["data"]
        return [
            d for d in devices if d["sku"] != "BaseGroup" and d["type"] == "devices.types.light"
        ]

    def turn_off_device(self, device_sku: str, device_id: str) -> dict[str, Any]:
        """
        POST /router/api/v1/device/control HTTP/1.1
        Host: https://openapi.api.govee.com
        Content-Type: application/json
        Govee-API-Key: xxxx

        {
        "requestId": "uuid",
        "payload": {
            "sku": "H605C",
            "device": "64:09:C5:32:37:36:2D:13",
            "capability": {
            "type": "devices.capabilities.on_off",
            "instance": "powerSwitch",
            "value": 0
            }
        }
        }
        """
        return self._call_api(
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

    def turn_on_device(self, device_sku: str, device_id: str) -> dict[str, Any]:
        return self._call_api(
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

    def get_device_state(self, device_sku: str, device_id: str) -> dict[str, Any]:
        """
        POST /router/api/v1/device/state HTTP/1.1
        Host: https://openapi.api.govee.com
        Content-Type: application/json
        Govee-API-Key: xxxx

        {
            "requestId": "uuid",
            "payload": {
                "sku": "H7143",
                "device": "52:8B:D4:AD:FC:45:5D:FE"
            }
        }
        """
        return self._call_api(
            "/device/state",
            method="POST",
            data={"requestId": "uuid", "payload": {"sku": device_sku, "device": device_id}},
        )

    def set_device_brightness(
        self, device_sku: str, device_id: str, brightness: int
    ) -> dict[str, Any]:
        """
        POST /router/api/v1/device/control HTTP/1.1
        Host: https://openapi.api.govee.com
        Content-Type: application/json
        Govee-API-Key: xxxx

        {
        "requestId": "1",
        "payload": {
            "sku": "H605C",
            "device": "64:09:C5:32:37:36:2D:13",
            "capability": {
            "type": "devices.capabilities.range",
            "instance": "brightness",
            "value": 50
            }
        }
        }
        """
        return self._call_api(
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
