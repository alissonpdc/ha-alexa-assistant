"""Tests for custom WebSocket commands."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from custom_components.alexa_assistant.const import DOMAIN
from custom_components.alexa_assistant.websocket import (
    WS_TYPE_GET_ALIASES,
    WS_TYPE_UPDATE_ALIASES,
    async_register_websocket_commands,
    ws_get_aliases,
    ws_update_aliases,
)


def test_ws_get_aliases_returns_entities_with_aliases_and_exclusion():
    """Verify ws_get_aliases returns map of entity_id to aliases and exclude_default_name."""
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
        mp.setattr(
            "custom_components.alexa_assistant.websocket.is_entity_default_name_excluded",
            lambda h, ent_id: ent_id == "light.sala",
        )
        msg = {"id": 42, "type": WS_TYPE_GET_ALIASES}
        ws_get_aliases(hass, connection, msg)

    connection.send_result.assert_called_once_with(
        42,
        {
            "light.sala": {"aliases": ["Luz da Sala", "Spot"], "exclude_default_name": True},
            "light.cozinha": {"aliases": ["Cozinha"], "exclude_default_name": False},
        },
    )


@pytest.mark.asyncio
async def test_ws_update_aliases_success():
    """Verify ws_update_aliases saves aliases and exclude_default_name."""
    hass = MagicMock()
    mock_storage = MagicMock()
    mock_storage.async_set_default_name_excluded = AsyncMock()
    hass.data = {DOMAIN: {"storage": mock_storage}}

    connection = MagicMock()
    mock_reg = MagicMock()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "custom_components.alexa_assistant.websocket.get_entity_registry",
            lambda h: mock_reg,
        )
        msg = {
            "id": 10,
            "type": WS_TYPE_UPDATE_ALIASES,
            "entity_id": "light.sala",
            "aliases": ["Spot da Sala", "Luz Teto"],
            "exclude_default_name": True,
        }
        await ws_update_aliases(hass, connection, msg)

    mock_storage.async_set_default_name_excluded.assert_awaited_once_with("light.sala", True)
    mock_reg.async_update_entity.assert_called_once_with("light.sala", aliases=["Spot da Sala", "Luz Teto"])
    connection.send_result.assert_called_once_with(
        10,
        {
            "success": True,
            "entity_id": "light.sala",
            "aliases": ["Spot da Sala", "Luz Teto"],
            "exclude_default_name": True,
        },
    )


@pytest.mark.asyncio
async def test_ws_update_aliases_blocks_empty_when_default_excluded():
    """Verify ws_update_aliases returns error when trying to remove only name."""
    hass = MagicMock()
    connection = MagicMock()

    msg = {
        "id": 11,
        "type": WS_TYPE_UPDATE_ALIASES,
        "entity_id": "light.sala",
        "aliases": [],
        "exclude_default_name": True,
    }
    await ws_update_aliases(hass, connection, msg)

    connection.send_error.assert_called_once_with(
        11,
        "invalid_data",
        "Não é possível remover o único nome.",
    )


def test_async_register_websocket_commands_registers_both_commands():
    """Verify async_register_websocket_commands calls async_register_command for both get and update."""
    hass = MagicMock()
    with pytest.MonkeyPatch.context() as mp:
        mock_ws_api = MagicMock()
        mock_ws_api.websocket_command.return_value = lambda f: f
        mp.setattr(
            "custom_components.alexa_assistant.websocket.websocket_api",
            mock_ws_api,
        )
        async_register_websocket_commands(hass)
        assert mock_ws_api.async_register_command.call_count == 2
