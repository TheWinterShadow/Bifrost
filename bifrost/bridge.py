"""HAP bridge setup and entry point."""

import logging
import os
import signal

import dotenv
from pyhap.accessory import Bridge
from pyhap.accessory_driver import AccessoryDriver

from bifrost.accessories.govee_light import discover_lights
from bifrost.utils.govee import GoveeClient

dotenv.load_dotenv(".envrc")

logger = logging.getLogger(__name__)

BRIDGE_NAME = "Bifrost"
PERSIST_FILE = os.environ.get("BIFROST_STATE_FILE", "bifrost.state")


def build_bridge(driver: AccessoryDriver) -> Bridge:
    """Construct the bridge and attach all accessories."""
    bridge = Bridge(driver, BRIDGE_NAME)

    govee = GoveeClient(os.environ["GOVEE_API_KEY"])
    for light in discover_lights(govee, driver):
        bridge.add_accessory(light)

    return bridge


def main() -> None:
    logging.basicConfig(level=logging.INFO)

    driver = AccessoryDriver(port=51826, persist_file=PERSIST_FILE)
    driver.add_accessory(build_bridge(driver))

    signal.signal(signal.SIGTERM, driver.signal_handler)
    driver.start()


if __name__ == "__main__":
    main()
