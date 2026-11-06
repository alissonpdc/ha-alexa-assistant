"""Expose manager for Alexa Smart Home."""
from __future__ import annotations

from collections.abc import Callable
import copy
import logging
from typing import Any

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
from .helpers import (
    build_alias_endpoint,
    get_entity_alexa_aliases,
    sanitize_alexa_name,
)

_LOGGER = logging.getLogger(__name__)


def is_entity_exposed(hass: HomeAssistant, entity_id: str) -> bool:
    """Check whether an entity is exposed to Alexa via exposed_entities.

    Example:
        exposed = is_entity_exposed(hass, "light.kitchen")
    """
    if async_should_expose is None:
        return False
    return bool(async_should_expose(hass, ASSISTANT_ALEXA, entity_id))


def resolve_directive_entity_id(endpoint_id: str) -> str:
    """Resolve directive endpointId to entity_id, stripping any alias suffix.

    Example:
        entity_id = resolve_directive_entity_id("switch#quintal_relay_piscina__alias_1")
    """
    clean_id = endpoint_id.split("__alias_")[0]
    return clean_id.replace("#", ".")


def process_discovery_endpoints(
    hass: Any,
    endpoints: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Sanitize endpoints and append alias endpoints for Alexa Discovery.

    Example:
        processed = process_discovery_endpoints(hass, endpoints)
    """
    result: list[dict[str, Any]] = []

    for ep in endpoints:
        ep_copy = copy.deepcopy(ep)
        raw_name = ep_copy.get("friendlyName", "")
        sanitized = sanitize_alexa_name(raw_name)
        ep_copy["friendlyName"] = sanitized or ep_copy.get("endpointId", "device")
        result.append(ep_copy)

        entity_id = resolve_directive_entity_id(ep_copy.get("endpointId", ""))
        aliases = get_entity_alexa_aliases(hass, entity_id)

        for i, alias in enumerate(aliases):
            if alias and alias != ep_copy["friendlyName"]:
                alias_ep = build_alias_endpoint(ep_copy, alias, i + 1)
                result.append(alias_ep)

    return result


class NativeAlexaExposeManager:
    """Manages patching AlexaConfig, Discovery and Directives for Alexa Assistant."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the expose manager.

        Example:
            manager = NativeAlexaExposeManager(hass)
        """
        self._hass: HomeAssistant = hass
        self._originals: dict[type, Callable[..., Any] | None] = {}
        self._unsub_listener: Callable[[], None] | None = None
        self._orig_discovery: Callable[..., Any] | None = None
        self._orig_load_entity: Callable[..., Any] | None = None
        self._orig_friendly_name: Any = None
        self._alexa_entity_class: type | None = None
        self._alexa_directive_class: type | None = None

    def apply_patch_to_class(self, target_class: type) -> None:
        """Patch should_expose on target_class to use is_entity_exposed.

        Example:
            manager.apply_patch_to_class(AlexaConfig)
        """
        self._originals[target_class] = getattr(target_class, "should_expose", None)
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
        original = self._originals.pop(target_class, None)
        if original is not None:
            setattr(target_class, "should_expose", original)
            _LOGGER.debug("Restored original should_expose on %s", target_class.__name__)

    def patch_discovery_and_directives(self) -> None:
        """Patch Alexa discovery, entity friendly_name and directive load_entity."""
        hass_ref = self._hass

        # 1. Patch AlexaEntity.friendly_name so base endpoint keeps its original name
        try:
            from homeassistant.components.alexa.entities import AlexaEntity

            self._alexa_entity_class = AlexaEntity
            self._orig_friendly_name = getattr(AlexaEntity, "friendly_name", None)

            def _patched_friendly_name(alexa_self: Any) -> str:
                name: str | None = getattr(alexa_self, "entity_conf", {}).get("name")
                if name is None:
                    entity = getattr(alexa_self, "entity", None)
                    if entity is not None and hasattr(entity, "name") and entity.name:
                        name = entity.name
                    elif hasattr(alexa_self, "entity_id"):
                        name = alexa_self.entity_id
                    else:
                        name = "device"
                return sanitize_alexa_name(name)

            setattr(AlexaEntity, "friendly_name", property(_patched_friendly_name))
            _LOGGER.debug("Successfully patched AlexaEntity.friendly_name")
        except Exception as err:
            _LOGGER.debug("Could not patch AlexaEntity.friendly_name: %s", err)

        # 2. Patch Alexa.Discovery handler to append cloned endpoints for aliases
        try:
            from homeassistant.components.alexa.handlers import HANDLERS

            key = ("Alexa.Discovery", "Discover")
            if key in HANDLERS:
                self._orig_discovery = HANDLERS[key]

                async def _patched_discovery(hass: Any, config: Any, directive: Any, context: Any) -> Any:
                    response = await self._orig_discovery(hass, config, directive, context)
                    payload: dict[str, Any] | None = None

                    if hasattr(response, "_response") and isinstance(response._response, dict):
                        payload = response._response.get("event", {}).get("payload")
                    elif hasattr(response, "payload") and isinstance(response.payload, dict):
                        payload = response.payload
                    elif isinstance(response, dict):
                        if "event" in response and isinstance(response["event"], dict):
                            payload = response["event"].get("payload")
                        elif "payload" in response and isinstance(response["payload"], dict):
                            payload = response["payload"]

                    if payload is not None and "endpoints" in payload and isinstance(payload["endpoints"], list):
                        payload["endpoints"] = process_discovery_endpoints(
                            hass_ref, payload["endpoints"]
                        )
                    return response

                HANDLERS[key] = _patched_discovery
                _LOGGER.debug("Successfully patched Alexa.Discovery handler")
        except Exception as err:
            _LOGGER.debug("Could not patch Alexa.Discovery handler: %s", err)

        # 3. Patch AlexaDirective.load_entity to resolve alias endpointId to base entity_id
        try:
            alexa_directive_class = None
            try:
                from homeassistant.components.alexa.smart_home import AlexaDirective
                alexa_directive_class = AlexaDirective
            except ImportError:
                from homeassistant.components.alexa.state_report import AlexaDirective
                alexa_directive_class = AlexaDirective

            if alexa_directive_class is not None:
                self._alexa_directive_class = alexa_directive_class
                self._orig_load_entity = alexa_directive_class.load_entity

                def _patched_load_entity(dir_self: Any, hass: Any, config: Any) -> None:
                    endpoint_data = None
                    if hasattr(dir_self, "_directive") and isinstance(dir_self._directive, dict):
                        endpoint_data = dir_self._directive.get("endpoint")

                    if isinstance(endpoint_data, dict) and "endpointId" in endpoint_data:
                        raw_id = str(endpoint_data["endpointId"])
                        if "__alias_" in raw_id:
                            endpoint_data["endpointId"] = raw_id.split("__alias_")[0]
                            try:
                                return self._orig_load_entity(dir_self, hass, config)
                            finally:
                                endpoint_data["endpointId"] = raw_id
                    return self._orig_load_entity(dir_self, hass, config)

                alexa_directive_class.load_entity = _patched_load_entity
                _LOGGER.debug("Successfully patched AlexaDirective.load_entity")
        except Exception as err:
            _LOGGER.debug("Could not patch AlexaDirective.load_entity: %s", err)

    def unpatch_discovery_and_directives(self) -> None:
        """Restore original discovery, friendly_name, and directive handlers."""
        if self._alexa_entity_class is not None and self._orig_friendly_name is not None:
            try:
                setattr(self._alexa_entity_class, "friendly_name", self._orig_friendly_name)
            except Exception:
                pass
            self._orig_friendly_name = None
            self._alexa_entity_class = None

        if self._orig_discovery is not None:
            try:
                from homeassistant.components.alexa.handlers import HANDLERS

                HANDLERS[("Alexa.Discovery", "Discover")] = self._orig_discovery
            except Exception:
                pass
            self._orig_discovery = None

        if self._alexa_directive_class is not None and self._orig_load_entity is not None:
            try:
                self._alexa_directive_class.load_entity = self._orig_load_entity
            except Exception:
                pass
            self._orig_load_entity = None
            self._alexa_directive_class = None

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
