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


@pytest.mark.asyncio
async def test_patched_discovery_handles_alexa_response_nested_structure():
    """Verify patched discovery updates endpoints in response._response['event']['payload']."""
    hass = MagicMock()
    manager = NativeAlexaExposeManager(hass)

    class FakeAlexaResponse:
        def __init__(self, endpoints):
            self._response = {
                "event": {
                    "header": {"namespace": "Alexa.Discovery", "name": "Discover.Response"},
                    "payload": {"endpoints": endpoints},
                }
            }

    raw_ep = [
        {
            "endpointId": "light#quintal_luz_grupo",
            "friendlyName": "Quintal Luz Grupo",
        }
    ]
    fake_response = FakeAlexaResponse(raw_ep)

    async def _fake_orig_discovery(hass, config, directive, context):
        return fake_response

    fake_handlers = {
        ("Alexa.Discovery", "Discover"): _fake_orig_discovery
    }

    with patch.dict("sys.modules", {"homeassistant.components.alexa.handlers": MagicMock(HANDLERS=fake_handlers)}), \
         patch("custom_components.alexa_assistant.expose.get_entity_alexa_aliases", return_value=["quintal1", "quintal2"]):
        manager.patch_discovery_and_directives()
        patched_handler = fake_handlers[("Alexa.Discovery", "Discover")]
        res = await patched_handler(hass, None, None, None)

        endpoints = res._response["event"]["payload"]["endpoints"]
        assert len(endpoints) == 3
        assert endpoints[0]["friendlyName"] == "Quintal Luz Grupo"
        assert endpoints[1]["friendlyName"] == "quintal1"
        assert endpoints[2]["friendlyName"] == "quintal2"

        manager.unpatch_discovery_and_directives()


def test_patched_load_entity_strips_and_restores_alias():
    """Verify patched load_entity temporarily strips __alias_ and restores it."""
    hass = MagicMock()
    manager = NativeAlexaExposeManager(hass)

    recorded_ids = []

    class FakeAlexaDirective:
        def __init__(self, endpoint_id):
            self._directive = {
                "endpoint": {"endpointId": endpoint_id}
            }

        def load_entity(self, hass, config):
            recorded_ids.append(self._directive["endpoint"]["endpointId"])

    fake_smart_home = MagicMock(AlexaDirective=FakeAlexaDirective)

    with patch.dict("sys.modules", {"homeassistant.components.alexa.smart_home": fake_smart_home}):
        manager.patch_discovery_and_directives()

        directive = FakeAlexaDirective("light#sala_luz_grupo__alias_1")
        directive.load_entity(hass, None)

        # Inside load_entity, alias was stripped
        assert recorded_ids == ["light#sala_luz_grupo"]
        # After load_entity, original endpointId is preserved for Alexa response
        assert directive._directive["endpoint"]["endpointId"] == "light#sala_luz_grupo__alias_1"

        manager.unpatch_discovery_and_directives()


def test_patched_alexa_entity_friendly_name_preserves_original_name():
    """Verify patched friendly_name returns state.name and does not use aliases[0]."""
    hass = MagicMock()
    manager = NativeAlexaExposeManager(hass)

    class FakeAlexaEntity:
        def __init__(self, name):
            self.entity = MagicMock(name=name)
            self.entity.name = name
            self.entity_conf = {}

        @property
        def friendly_name(self):
            return "Overwritten Alias 0"

    fake_entities_mod = MagicMock(AlexaEntity=FakeAlexaEntity)

    with patch.dict("sys.modules", {"homeassistant.components.alexa.entities": fake_entities_mod}):
        manager.patch_discovery_and_directives()

        entity_inst = FakeAlexaEntity("Luz da Sala")
        # Should now return the actual entity name, not the overwritten alias
        assert entity_inst.friendly_name == "Luz da Sala"

        manager.unpatch_discovery_and_directives()
        assert entity_inst.friendly_name == "Overwritten Alias 0"
