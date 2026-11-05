"""Expose manager for Alexa Smart Home."""
from collections.abc import Callable
import logging
from typing import Optional

try:
    from homeassistant.components.homeassistant.exposed_entities import (
        async_listen_entity_updates,
        async_should_expose,
    )
    from homeassistant.core import HomeAssistant
except ImportError:
    async_should_expose = None
    async_listen_entity_updates = None
    HomeAssistant = object

from .const import ASSISTANT_ALEXA

_LOGGER = logging.getLogger(__name__)


def is_entity_exposed(hass: HomeAssistant, entity_id: str) -> bool:
    """Check whether an entity is exposed to Alexa via exposed_entities.

    Example:
        exposed = is_entity_exposed(hass, "light.kitchen")
    """
    if async_should_expose is None:
        return False
    return bool(async_should_expose(hass, ASSISTANT_ALEXA, entity_id))


class NativeAlexaExposeManager:
    """Manages patching AlexaConfig to consult Home Assistant native exposed_entities."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the expose manager.

        Example:
            manager = NativeAlexaExposeManager(hass)
        """
        self._hass: HomeAssistant = hass
        self._original_should_expose: Optional[Callable[[object, str], bool]] = None
        self._patched_class: Optional[type] = None
        self._unsub_listener: Optional[Callable[[], None]] = None

    def apply_patch_to_class(self, target_class: type) -> None:
        """Patch should_expose on target_class to use is_entity_exposed.

        Example:
            manager.apply_patch_to_class(AlexaConfig)
        """
        self._patched_class = target_class
        self._original_should_expose = getattr(target_class, "should_expose", None)
        hass_ref = self._hass

        def _patched_should_expose(instance: object, entity_id: str) -> bool:
            return is_entity_exposed(hass_ref, entity_id)

        setattr(target_class, "should_expose", _patched_should_expose)
        _LOGGER.debug("Patched should_expose on %s", target_class.__name__)

    def remove_patch_from_class(self, target_class: type) -> None:
        """Restore original should_expose on target_class.

        Example:
            manager.remove_patch_from_class(AlexaConfig)
        """
        if self._original_should_expose is not None:
            setattr(target_class, "should_expose", self._original_should_expose)
            _LOGGER.debug("Restored original should_expose on %s", target_class.__name__)
            self._original_should_expose = None
        self._patched_class = None

    def start_listening(self) -> None:
        """Register active listener for cloud.alexa to activate it in UI.

        Example:
            manager.start_listening()
        """
        if async_listen_entity_updates is None:
            return

        def _on_entity_update() -> None:
            _LOGGER.debug("Alexa entity exposure updated in UI")

        self._unsub_listener = async_listen_entity_updates(
            self._hass, ASSISTANT_ALEXA, _on_entity_update
        )

    def stop_listening(self) -> None:
        """Unregister active listener.

        Example:
            manager.stop_listening()
        """
        if self._unsub_listener is not None:
            self._unsub_listener()
            self._unsub_listener = None
