"""Alexa Assistant integration."""
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
from .panel import async_register_alexa_panel, async_unregister_alexa_panel
from .websocket import async_register_websocket_commands

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the integration via YAML.

    Example:
        await async_setup(hass, config)
    """
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Alexa Assistant from a config entry.

    Example:
        await async_setup_entry(hass, entry)
    """
    hass.data.setdefault(DOMAIN, {})
    manager = NativeAlexaExposeManager(hass)

    # Patch AbstractConfig
    try:
        from homeassistant.components.alexa.config import AbstractConfig

        manager.apply_patch_to_class(AbstractConfig)
        _LOGGER.debug("Successfully patched AbstractConfig.should_expose")
    except Exception as e:
        _LOGGER.debug("AbstractConfig patch failed: %s", e)

    # Patch AlexaConfig
    try:
        from homeassistant.components.alexa.smart_home import AlexaConfig

        manager.apply_patch_to_class(AlexaConfig)
        _LOGGER.debug("Successfully patched AlexaConfig.should_expose")
    except Exception as e:
        _LOGGER.debug("AlexaConfig patch failed: %s", e)

    manager.start_listening()
    manager.patch_discovery_and_directives()
    async_register_websocket_commands(hass)
    hass.data[DOMAIN][entry.entry_id] = manager
    await async_register_alexa_panel(hass)
    _LOGGER.info("Alexa Assistant successfully enabled")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry.

    Example:
        await async_unload_entry(hass, entry)
    """
    await async_unregister_alexa_panel(hass)
    manager = hass.data[DOMAIN].pop(entry.entry_id, None)
    if manager is not None:
        try:
            from homeassistant.components.alexa.config import AbstractConfig

            manager.remove_patch_from_class(AbstractConfig)
        except Exception:
            pass
        try:
            from homeassistant.components.alexa.smart_home import AlexaConfig

            manager.remove_patch_from_class(AlexaConfig)
        except Exception:
            pass
        manager.unpatch_discovery_and_directives()
        manager.stop_listening()
    return True
