"""HAP bridge setup and entry point."""

import asyncio
import logging
import os
import signal

import dotenv
from pyhap.accessory import Bridge
from pyhap.accessory_driver import AccessoryDriver

from bifrost.accessories.govee_air_purifier import discover_air_purifiers
from bifrost.accessories.govee_light import discover_lights
from bifrost.accessories.smartrent_thermostat import discover_thermostats
from bifrost.utils.govee import GoveeClient
from bifrost.utils.smartrent import SmartRentClient

dotenv.load_dotenv(".envrc")

logger = logging.getLogger(__name__)

BRIDGE_NAME = "Bifrost"
PERSIST_FILE = os.environ.get("BIFROST_STATE_FILE", "bifrost.state")


def build_bridge(driver: AccessoryDriver) -> Bridge:
    """Construct the bridge and attach all accessories."""
    bridge = Bridge(driver, BRIDGE_NAME)
    accessories = []

    # Govee devices (sync API)
    api_key = os.environ.get("GOVEE_API_KEY")
    if api_key:
        govee = GoveeClient(api_key)
        accessories.extend(discover_lights(govee, driver))
        accessories.extend(discover_air_purifiers(govee, driver))
    else:
        logger.warning("GOVEE_API_KEY is not set — skipping Govee devices")

    # SmartRent devices (async API)
    sr_email = os.environ.get("SMARTRENT_EMAIL")
    sr_password = os.environ.get("SMARTRENT_PASSWORD")
    if sr_email and sr_password:
        sr_client = SmartRentClient(sr_email, sr_password)
        inventory = asyncio.run(sr_client.connect())
        accessories.extend(discover_thermostats(inventory.thermostats, driver))
    else:
        logger.warning("SMARTRENT_EMAIL/SMARTRENT_PASSWORD not set — skipping SmartRent devices")

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
