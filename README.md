# Bifrost

Apple HomeKit bridge for Govee and Google Nest devices, built on [HAP-python](https://github.com/ikalchev/HAP-python).

---

## Requirements

- [Docker](https://docs.docker.com/get-docker/) (for deployment)
- [Hatch](https://hatch.pypa.io/latest/install/) (for local development)
- Python 3.11+
- A [Govee API key](https://developer.govee.com/docs/support-zigbee-wifi-ble-devices)

---

## Deployment

### 1. Pull the image

```bash
docker pull thewintersshadow/bifrost:latest
```

### 2. Run the container

```bash
docker run --rm \
  -p 51826:51826/tcp \
  -p 51826:51826/udp \
  -v bifrost-state:/data \
  -e GOVEE_API_KEY=your-api-key \
  --name bifrost \
  thewintersshadow/bifrost:latest
```

Or with Hatch (local build):

```bash
hatch run docker:build
hatch run docker:run your-api-key
```

The bridge will print a **HomeKit pairing QR code and setup code** to stdout on the first run.
Open the **Home** app on your iPhone or iPad → **Add Accessory** → scan the code or enter it manually.

> The pairing state is written to `/data/bifrost.state` inside the container and persisted in
> the `bifrost-state` Docker volume, so re-creating the container does **not** require re-pairing.

### 3. Running persistently (Docker Compose)

```yaml
services:
  bifrost:
    image: thewintersshadow/bifrost:latest
    restart: unless-stopped
    network_mode: host        # required for mDNS/Bonjour discovery
    environment:
      - GOVEE_API_KEY=your-api-key
    volumes:
      - bifrost-state:/data

volumes:
  bifrost-state:
```

Then start it with:

```bash
docker compose up -d
```

> `network_mode: host` is required on Linux so that the bridge is visible on your local network
> via mDNS. On macOS Docker Desktop, host networking behaves differently — use the explicit port
> mapping (`-p 51826:51826/tcp -p 51826:51826/udp`) instead.

---

## Local development

```bash
# Install the package in editable mode
pip install -e .

# Or use Hatch to manage the environment
hatch shell

# Lint & format
hatch run lint
hatch run fmt

# Run tests
hatch run test

# Run the bridge locally (no Docker)
GOVEE_API_KEY=your-api-key bifrost
```

---

## Adding an accessory

Each device type is a Python class that extends `pyhap.accessory.Accessory`.
Place new accessories in `bifrost/accessories/`.

### Step-by-step

1. **Create the file** — e.g. `bifrost/accessories/my_light.py`

2. **Subclass `Light`** and implement the three required methods:

```python
from bifrost.accessories.light import Light

class MyLight(Light):
    def __init__(self, driver, name: str, *, device_id: str):
        super().__init__(driver, name)
        self.device_id = device_id

    def _set_on(self, value: bool) -> None:
        # Send on/off command to the real device
        pass

    def _set_brightness(self, value: int) -> None:
        # Send brightness (0–100) to the real device
        pass

    async def _fetch_state(self) -> tuple[bool, int]:
        # Poll the real device and return (on, brightness)
        return True, 100
```

1. **Register it in the bridge** — open `bifrost/bridge.py` and add your accessory to `build_bridge`:

```python
from bifrost.accessories.my_light import MyLight

def build_bridge(driver: AccessoryDriver) -> Bridge:
    bridge = Bridge(driver, BRIDGE_NAME)
    bridge.add_accessory(MyLight(driver, "Living Room Light", device_id="AA:BB:CC:DD"))
    return bridge
```

1. **Rebuild the Docker image** after any code change:

```bash
hatch run docker:build
```

### Useful HAP service names

| Device type        | Service string        | Category constant     |
| ------------------ | --------------------- | --------------------- |
| Light bulb         | `"Lightbulb"`         | `CATEGORY_LIGHTBULB`  |
| Switch             | `"Switch"`            | `CATEGORY_SWITCH`     |
| Thermostat         | `"Thermostat"`        | `CATEGORY_THERMOSTAT` |
| Temperature sensor | `"TemperatureSensor"` | `CATEGORY_SENSOR`     |
| Fan                | `"Fan"`               | `CATEGORY_FAN`        |

Full list: [HAP-python service definitions](https://github.com/ikalchev/HAP-python/tree/master/pyhap/resources)
