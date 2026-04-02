# Bifrost

Apple HomeKit bridge for Govee and Google Nest devices, built on [HAP-python](https://github.com/ikalchev/HAP-python).

---

## Requirements

- [Docker](https://docs.docker.com/get-docker/) (for deployment)
- [Hatch](https://hatch.pypa.io/latest/install/) (for local development)
- Python 3.11+

---

## Deployment

### 1. Build the image

```bash
hatch run docker:build
# or directly:
docker build -t bifrost:latest .
```

### 2. Run the container

```bash
hatch run docker:run
# or directly:
docker run --rm \
  -p 51826:51826/tcp \
  -p 51826:51826/udp \
  -v bifrost-state:/data \
  --name bifrost \
  bifrost:latest
```

The bridge will print a **HomeKit pairing QR code and setup code** to stdout on the first run.
Open the **Home** app on your iPhone or iPad → **Add Accessory** → scan the code or enter it manually.

> The pairing state is written to `/data/bifrost.state` inside the container and persisted in
> the `bifrost-state` Docker volume, so re-creating the container does **not** require re-pairing.

### 3. Running persistently (Docker Compose)

Create a `docker-compose.yml` alongside this repo:

```yaml
services:
  bifrost:
    image: bifrost:latest
    build: .
    restart: unless-stopped
    network_mode: host        # required for mDNS/Bonjour discovery
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

### 4. Publishing the image

```bash
hatch run docker:push ghcr.io/your-org/bifrost:latest
```

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
bifrost
```

---

## Adding an accessory

Each device type is a Python class that extends `pyhap.accessory.Accessory`.
Place new accessories in `bifrost/accessories/`.

### Step-by-step

1. **Create the file** — e.g. `bifrost/accessories/my_light.py`

2. **Subclass `Accessory`** and declare HAP services/characteristics:

```python
from pyhap.accessory import Accessory
from pyhap.const import CATEGORY_LIGHTBULB

class MyLight(Accessory):
    category = CATEGORY_LIGHTBULB

    def __init__(self, driver, name: str, *, device_id: str):
        super().__init__(driver, name)
        self.device_id = device_id

        # Grab the built-in Lightbulb service
        svc = self.add_preload_service("Lightbulb")
        self.char_on = svc.configure_char("On", setter_callback=self._set_on)
        self.char_brightness = svc.configure_char(
            "Brightness", setter_callback=self._set_brightness
        )

    # Called by HomeKit when the user toggles the light
    def _set_on(self, value: bool) -> None:
        # TODO: send command to the real device
        pass

    def _set_brightness(self, value: int) -> None:
        # TODO: send command to the real device (value is 0–100)
        pass

    # Called on a background loop to push current device state to HomeKit
    @Accessory.run_at_interval(30)
    async def run(self) -> None:
        # TODO: fetch state from the real device and update characteristics
        # self.char_on.set_value(current_on)
        # self.char_brightness.set_value(current_brightness)
        pass
```

1. **Register it in the bridge** — open `bifrost/bridge.py` and add your accessory to
   `build_bridge`:

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

| Device type       | Service string        | Category constant     |
| ----------------- | --------------------- | --------------------- |
| Light bulb        | `"Lightbulb"`         | `CATEGORY_LIGHTBULB`  |
| Switch            | `"Switch"`            | `CATEGORY_SWITCH`     |
| Thermostat        | `"Thermostat"`        | `CATEGORY_THERMOSTAT` |
| Temperature sensor| `"TemperatureSensor"` | `CATEGORY_SENSOR`     |
| Fan               | `"Fan"`               | `CATEGORY_FAN`        |

Full list: [HAP-python service definitions](https://github.com/ikalchev/HAP-python/tree/master/pyhap/resources)
