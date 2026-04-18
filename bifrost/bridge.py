"""HAP bridge setup and entry point."""

import logging
import os
import signal

import dotenv
from pyhap.accessory import Bridge
from pyhap.accessory_driver import AccessoryDriver

from bifrost.accessories.govee_air_purifier import discover_air_purifiers
from bifrost.accessories.govee_light import discover_lights
from bifrost.utils.govee import GoveeClient

dotenv.load_dotenv(".envrc")

logger = logging.getLogger(__name__)

BRIDGE_NAME = "Bifrost"
PERSIST_FILE = os.environ.get("BIFROST_STATE_FILE", "bifrost.state")


def build_bridge(driver: AccessoryDriver) -> Bridge:
    """Construct the bridge and attach all accessories."""
    bridge = Bridge(driver, BRIDGE_NAME)

    api_key = os.environ.get("GOVEE_API_KEY")
    if not api_key:
        logger.error("GOVEE_API_KEY is not set — no accessories will be loaded")
        return bridge

    govee = GoveeClient(api_key)

    accessories = [
        *discover_lights(govee, driver),
        *discover_air_purifiers(govee, driver),
    ]
    for accessory in accessories:
        bridge.add_accessory(accessory)
    logger.info("Bridge ready with %d accessory(s)", len(accessories))

    return bridge


def main() -> None:
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    address = os.environ.get("BIFROST_ADDRESS") or None
    logger.info(
        "Starting Bifrost — address=%s port=51826 state=%s log_level=%s",
        address or "auto",
        PERSIST_FILE,
        log_level,
    )

    driver = AccessoryDriver(port=51826, persist_file=PERSIST_FILE, address=address)
    driver.add_accessory(build_bridge(driver))

    signal.signal(signal.SIGTERM, driver.signal_handler)
    driver.start()


if __name__ == "__main__":
    main()
