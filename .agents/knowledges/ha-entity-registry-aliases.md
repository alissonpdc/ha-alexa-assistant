# Home Assistant Entity Registry Aliases in WebSocket & Storage

### Symptom
- Calling WebSocket `config/entity_registry/list` returns entity metadata but `aliases` (or `aliases_v2`) is completely missing or empty, causing UI to lose aliases on page refresh even though `config/entity_registry/update` persists them to `.storage/core.entity_registry`.
- The browser caches custom panel JS (`panel.js`) indefinitely if `module_url` doesn't include a cache-buster query string.

### Root Cause
- In Home Assistant Core, `websocket_list_entities` uses `entry.partial_json_repr` to build the list response. `partial_json_repr` intentionally strips out heavy/optional fields including voice aliases to keep list payloads small.
- Individual entity detail (`config/entity_registry/get`) has aliases, but iterating it over 100+ entities is inefficient.
- Modern Home Assistant (2024+) stores voice aliases in `aliases_v2` (which can contain `null` for `COMPUTED_NAME`), while legacy `aliases` key on disk is `[]`.

### Solution
1. Register a dedicated custom WebSocket command in the integration (`alexa_assistant/aliases`) that queries `er.async_get(hass)` in memory and returns `{ [entity_id]: sanitized_aliases }`.
2. In the custom panel, query this dedicated route in `Promise.all` alongside registry lists.
3. Append `?v=X.Y.Z` cache buster to `module_url` in `async_register_panel` so browser loads fresh frontend script.
