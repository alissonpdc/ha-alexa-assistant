"""Alexa Native Expose integration."""
import logging
from typing import Any

try:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
except ImportError:
    ConfigEntry = object
    HomeAssistant = object

from .const import DOMAIN
from .expose import NativeAlexaExposeManager

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the integration via YAML.

    Example:
        await async_setup(hass, config)
    """
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Alexa Native Expose from a config entry.

    Example:
        await async_setup_entry(hass, entry)
    """
    hass.data.setdefault(DOMAIN, {})
    manager = NativeAlexaExposeManager(hass)

    try:
        from homeassistant.components.alexa.config import AlexaConfig

        manager.apply_patch_to_class(AlexaConfig)
    except ImportError:
        _LOGGER.debug("AlexaConfig not loaded in this environment")

    manager.start_listening()
    hass.data[DOMAIN][entry.entry_id] = manager
    _LOGGER.info("Alexa Native Expose successfully enabled")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry.

    Example:
        await async_unload_entry(hass, entry)
    """
    manager = hass.data[DOMAIN].pop(entry.entry_id, None)
    if manager is not None:
        try:
            from homeassistant.components.alexa.config import AlexaConfig

            manager.remove_patch_from_class(AlexaConfig)
        except ImportError:
            pass
        manager.stop_listening()
    return True
