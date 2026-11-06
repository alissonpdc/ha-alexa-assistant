"""Tests for Config Flow."""
import pytest
from unittest.mock import MagicMock, patch

from custom_components.alexa_assistant.config_flow import AlexaAssistantConfigFlow
from custom_components.alexa_assistant.const import DOMAIN


async def test_config_flow_single_instance_creates_entry():
    """Verify config flow creates entry on user step."""
    flow = AlexaAssistantConfigFlow()
    flow.hass = MagicMock()
    flow._async_current_entries = MagicMock(return_value=[])

    result = await flow.async_step_user(user_input={})

    assert result["type"] == "create_entry"
    assert result["title"] == "Alexa Assistant"
    assert result["data"] == {}


async def test_config_flow_aborts_if_already_configured():
    """Verify config flow aborts if already configured."""
    flow = AlexaAssistantConfigFlow()
    flow.hass = MagicMock()
    flow._async_current_entries = MagicMock(return_value=[MagicMock()])

    result = await flow.async_step_user(user_input={})

    assert result["type"] == "abort"
    assert result["reason"] == "single_instance_allowed"
