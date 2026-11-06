"""Tests for custom WebSocket commands."""
import pytest
from unittest.mock import MagicMock

from custom_components.alexa_assistant.websocket import (
    WS_TYPE_GET_ALIASES,
    async_register_websocket_commands,
    ws_get_aliases,
)


def test_ws_get_aliases_returns_entities_with_aliases():
    """Verify ws_get_aliases returns map of entity_id to aliases."""
    hass = MagicMock()
    connection = MagicMock()
    mock_reg = MagicMock()
    mock_reg.entities = ["light.sala", "light.cozinha", "switch.sem_alias"]

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "custom_components.alexa_assistant.websocket.get_entity_registry",
            lambda h: mock_reg,
        )
        mp.setattr(
            "custom_components.alexa_assistant.websocket.get_entity_alexa_aliases",
            lambda h, ent_id: ["Luz da Sala", "Spot"] if ent_id == "light.sala" else ([] if ent_id == "switch.sem_alias" else ["Cozinha"]),
        )
        msg = {"id": 42, "type": WS_TYPE_GET_ALIASES}
        ws_get_aliases(hass, connection, msg)

    connection.send_result.assert_called_once_with(
        42,
        {
            "light.sala": ["Luz da Sala", "Spot"],
            "light.cozinha": ["Cozinha"],
        },
    )


def test_async_register_websocket_commands_registers_with_ha():
    """Verify async_register_websocket_commands calls async_register_command."""
    hass = MagicMock()
    with pytest.MonkeyPatch.context() as mp:
        mock_ws_api = MagicMock()
        mock_ws_api.websocket_command.return_value = lambda f: f
        mp.setattr(
            "custom_components.alexa_assistant.websocket.websocket_api",
            mock_ws_api,
        )
        async_register_websocket_commands(hass)
        mock_ws_api.async_register_command.assert_called_once()
