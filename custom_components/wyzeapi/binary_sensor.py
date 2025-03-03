import logging
import time
from datetime import timedelta
from typing import List

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    DEVICE_CLASS_MOTION
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant
from wyzeapy.base_client import Device, AccessTokenError
from wyzeapy.client import Client
from wyzeapy.types import PropertyIDs

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
ATTRIBUTION = "Data provided by Wyze"
SCAN_INTERVAL = timedelta(seconds=10)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities):
    _LOGGER.debug("""Creating new WyzeApi binary sensor component""")
    client: Client = hass.data[DOMAIN][config_entry.entry_id]

    def get_cameras() -> List[Device]:
        try:
            return client.get_cameras()
        except AccessTokenError as e:
            _LOGGER.warning(e)
            client.reauthenticate()
            return client.get_cameras()

    cameras = [WyzeCameraMotion(client, camera) for camera in await hass.async_add_executor_job(get_cameras)]

    async_add_entities(cameras, True)


class WyzeCameraMotion(BinarySensorEntity):
    _on: bool
    _available: bool

    def __init__(self, wyzeapi_client: Client, device: Device):
        self._client = wyzeapi_client
        self._device = device
        self._last_event = int(str(int(time.time())) + "000")

    @property
    def device_info(self):
        return {
            "identifiers": {
                (DOMAIN, self._device.mac)
            },
            "name": self.name,
            "manufacturer": "WyzeLabs",
            "model": self._device.product_model
        }

    @property
    def available(self) -> bool:
        return self._available

    @property
    def name(self):
        """Return the display name of this switch."""
        return self._device.nickname

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._on

    @property
    def unique_id(self):
        return "{}-motion".format(self._device.mac)

    @property
    def device_state_attributes(self):
        """Return device attributes of the entity."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            "state": self.is_on,
            "available": self.available,
            "device model": self._device.product_model,
            "mac": self.unique_id
        }

    @property
    def device_class(self):
        return DEVICE_CLASS_MOTION

    def update(self):
        try:
            device_info = self._client.get_info(self._device)
        except AccessTokenError:
            self._client.reauthenticate()
            device_info = self._client.get_info(self._device)

        for property_id, value in device_info:
            if property_id == PropertyIDs.AVAILABLE:
                self._available = True if value == "1" else False

        latest_event = self._client.get_latest_event(self._device)
        if latest_event is not None:
            if latest_event.event_ts > self._last_event:
                self._on = True
                self._last_event = latest_event.event_ts
            else:
                self._on = False
                self._last_event = latest_event.event_ts
        else:
            self._on = False


