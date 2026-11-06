"""Tests for Alexa Assistant helper functions."""
import pytest
from unittest.mock import MagicMock

from custom_components.alexa_assistant.helpers import (
    build_alias_endpoint,
    get_entity_alexa_aliases,
    sanitize_alexa_name,
)


@pytest.mark.parametrize(
    ("raw_name", "expected"),
    [
        ("quintal_relay_piscina", "quintal relay piscina"),
        ("Luz Sala (Teto)", "Luz Sala Teto"),
        ("Lâmpada 1 - Principal & Plafon!", "Lâmpada 1 Principal Plafon"),
        ("Cafeteira (Smart-Plug) #2", "Cafeteira Smart Plug 2"),
        ("Ar-Condicionado [Quarto]", "Ar Condicionado Quarto"),
        ("Luz  da   Cozinha...", "Luz da Cozinha"),
        ("   ", ""),
        ("", ""),
    ],
)
def test_sanitize_alexa_name_strips_special_characters(raw_name: str, expected: str):
    """Verify sanitize_alexa_name leaves only letters, numbers and single spaces."""
    assert sanitize_alexa_name(raw_name) == expected


def test_build_alias_endpoint_creates_unique_endpoint_id():
    """Verify build_alias_endpoint generates proper cloned endpoint."""
    base_endpoint = {
        "endpointId": "switch#quintal_relay_piscina",
        "friendlyName": "quintal relay piscina",
        "description": "switch.quintal_relay_piscina via Home Assistant",
        "capabilities": [{"type": "AlexaInterface"}],
        "displayCategories": ["SWITCH"],
    }

    alias_endpoint = build_alias_endpoint(base_endpoint, "Bomba da Piscina", 1)

    assert alias_endpoint["endpointId"] == "switch#quintal_relay_piscina__alias_1"
    assert alias_endpoint["friendlyName"] == "Bomba da Piscina"
    assert alias_endpoint["description"] == "Bomba da Piscina via Home Assistant"
    assert alias_endpoint["capabilities"] == base_endpoint["capabilities"]
    assert alias_endpoint["displayCategories"] == base_endpoint["displayCategories"]


def test_get_entity_alexa_aliases_returns_up_to_max_sanitized():
    """Verify get_entity_alexa_aliases limits to 5 and sanitizes."""
    hass = MagicMock()
    mock_registry = MagicMock()
    mock_entry = MagicMock()
    mock_entry.aliases = [
        "Piscina-Grande",
        "Bomba_Piscina",
        "Motor (Piscina)",
        "Área Externa",
        "Luz #5",
        "Excesso 6",
    ]
    mock_registry.async_get.return_value = mock_entry

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "custom_components.alexa_assistant.helpers.get_entity_registry",
            lambda h: mock_registry,
        )
        aliases = get_entity_alexa_aliases(hass, "switch.quintal_relay_piscina", max_aliases=5)

    assert len(aliases) == 5
    assert aliases == [
        "Piscina Grande",
        "Bomba Piscina",
        "Motor Piscina",
        "Área Externa",
        "Luz 5",
    ]


def test_get_entity_alexa_aliases_supports_aliases_v2_with_none_and_strings():
    """Verify get_entity_alexa_aliases handles aliases_v2 containing null and strings."""
    hass = MagicMock()
    mock_registry = MagicMock()
    mock_entry = MagicMock()
    mock_entry.aliases = []
    mock_entry.aliases_v2 = [None, "Luz-Principal", "Spot_Teto"]
    mock_registry.async_get.return_value = mock_entry

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "custom_components.alexa_assistant.helpers.get_entity_registry",
            lambda h: mock_registry,
        )
        aliases = get_entity_alexa_aliases(hass, "light.sala")

    assert aliases == ["Luz Principal", "Spot Teto"]
