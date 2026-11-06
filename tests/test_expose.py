"""Tests for Alexa Assistant."""
import pytest
from unittest.mock import MagicMock, patch

from custom_components.alexa_assistant.const import DOMAIN, ASSISTANT_ALEXA
from custom_components.alexa_assistant.expose import (
    NativeAlexaExposeManager,
    is_entity_exposed,
)


def test_is_entity_exposed_returns_true_when_helper_returns_true():
    """Verify is_entity_exposed returns True when exposed_entities says True."""
    hass = MagicMock()
    with patch(
        "custom_components.alexa_assistant.expose.async_should_expose",
        return_value=True,
    ):
        result = is_entity_exposed(hass, "light.living_room")
        assert result is True


def test_is_entity_exposed_returns_false_when_helper_returns_false():
    """Verify is_entity_exposed returns False when exposed_entities says False."""
    hass = MagicMock()
    with patch(
        "custom_components.alexa_assistant.expose.async_should_expose",
        return_value=False,
    ):
        result = is_entity_exposed(hass, "light.secret_lamp")
        assert result is False


def test_manager_patches_and_unpatches_alexa_config():
    """Verify NativeAlexaExposeManager patches AlexaConfig and restores it cleanly."""
    hass = MagicMock()

    class FakeAlexaConfig:
        def __init__(self):
            self.hass = hass

        def should_expose(self, entity_id: str) -> bool:
            return False

    fake_config = FakeAlexaConfig()
    manager = NativeAlexaExposeManager(hass)

    with patch(
        "custom_components.alexa_assistant.expose.async_should_expose",
        side_effect=lambda h, assistant, ent_id: ent_id == "light.allowed",
    ):
        # Before patch
        assert fake_config.should_expose("light.allowed") is False

        # Apply patch to FakeAlexaConfig class
        manager.apply_patch_to_class(FakeAlexaConfig)
        assert fake_config.should_expose("light.allowed") is True
        assert fake_config.should_expose("light.blocked") is False

        # Remove patch
        manager.remove_patch_from_class(FakeAlexaConfig)
        assert fake_config.should_expose("light.allowed") is False


def test_resolve_directive_entity_id_strips_alias_suffix():
    """Verify resolve_directive_entity_id handles base and alias endpoint IDs."""
    from custom_components.alexa_assistant.expose import resolve_directive_entity_id

    # Normal endpointId
    assert resolve_directive_entity_id("light#sala_luz") == "light.sala_luz"

    # Alias endpointId
    assert resolve_directive_entity_id("switch#quintal_relay_piscina__alias_1") == "switch.quintal_relay_piscina"
    assert resolve_directive_entity_id("light#quarto__alias_5") == "light.quarto"


def test_process_discovery_endpoints_sanitizes_and_injects_aliases():
    """Verify process_discovery_endpoints sanitizes friendlyName and creates alias endpoints."""
    from custom_components.alexa_assistant.expose import process_discovery_endpoints

    hass = MagicMock()
    raw_endpoints = [
        {
            "endpointId": "light#sala_teto_principal",
            "friendlyName": "Sala - Luz (Teto) #1",
            "description": "light.sala_teto_principal via Home Assistant",
            "capabilities": [{"type": "AlexaInterface"}],
            "displayCategories": ["LIGHT"],
        }
    ]

    with patch(
        "custom_components.alexa_assistant.expose.get_entity_alexa_aliases",
        return_value=["Plafon da Sala", "Luz de Teto"],
    ):
        processed = process_discovery_endpoints(hass, raw_endpoints)

    # Must contain 1 base + 2 alias endpoints = 3 endpoints
    assert len(processed) == 3

    # Base endpoint sanitized
    assert processed[0]["endpointId"] == "light#sala_teto_principal"
    assert processed[0]["friendlyName"] == "Sala Luz Teto 1"

    # Alias 1
    assert processed[1]["endpointId"] == "light#sala_teto_principal__alias_1"
    assert processed[1]["friendlyName"] == "Plafon da Sala"

    # Alias 2
    assert processed[2]["endpointId"] == "light#sala_teto_principal__alias_2"
    assert processed[2]["friendlyName"] == "Luz de Teto"
