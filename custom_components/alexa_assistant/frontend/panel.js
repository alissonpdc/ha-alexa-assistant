/**
 * Alexa Assistant - Custom Sidebar Panel
 * Area & Type Hierarchical Explorer with Voice Aliases and strict Alexa sanitization.
 * Implements refined UX Model 3:
 * - 2-level distinct filter cards: Area (Room) & Device Type (Domain) with 'All' options
 * - Search bar filtering within active selections
 * - Exposure segmentation: All, Exposed, Hidden
 * - Exposed entities ordered before Hidden entities
 * - Base voice name locked as first item, followed by up to 5 voice aliases
 * - Microphone icon indicator and instant checkmark (+) button for alias submission
 * - Batch Expose All and Hide All buttons
 * - Mobile responsive: touch-friendly controls, overflow-proof cards, and horizontal filter chips
 */
class AlexaAssistantPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._exposed = {};
    this._aliases = {}; // entity_id -> string[]
    this._excludedDefaultNames = {}; // entity_id -> boolean
    this._areas = {}; // entity_id -> area_name
    this._allAreas = [];
    this._allDomains = [];
    this._activeArea = "all";
    this._activeDomain = "all";
    this._exposureFilter = "all"; // 'all', 'exposed', 'hidden'
    this._searchQuery = "";
    this._loading = true;
    this._updating = new Set();
    this._clearedInputs = new Set();
  }

  _isDarkMode() {
    if (this._hass?.themes?.darkMode !== undefined) {
      return Boolean(this._hass.themes.darkMode);
    }
    return Boolean(window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches);
  }

  set hass(hass) {
    const isFirst = !this._hass;
    this._hass = hass;
    if (isFirst) {
      this._loadData();
    }
  }

  _sanitize(name) {
    if (!name) return "";
    try {
      const normalized = String(name).normalize("NFC");
      return normalized
        .replace(/[^\p{L}\p{N}\p{M}\s]/gu, " ")
        .normalize("NFC")
        .replace(/\s+/g, " ")
        .trim();
    } catch {
      return String(name)
        .replace(/[^a-zA-Z0-9\u00C0-\u00FF\s]/g, " ")
        .replace(/\s+/g, " ")
        .trim();
    }
  }

  async _loadData() {
    this._loading = true;
    this._render();
    try {
      const [exposedRes, registryRes, areasRes, devicesRes, aliasesRes] = await Promise.all([
        this._hass.callWS({ type: "homeassistant/expose_entity/list" }).catch(() => ({})),
        this._hass.callWS({ type: "config/entity_registry/list" }).catch(() => []),
        this._hass.callWS({ type: "config/area_registry/list" }).catch(() => []),
        this._hass.callWS({ type: "config/device_registry/list" }).catch(() => []),
        this._hass.callWS({ type: "alexa_assistant/aliases" }).catch(() => ({})),
      ]);

      this._exposed = exposedRes?.exposed_entities || {};

      const areaMap = {};
      if (Array.isArray(areasRes)) {
        for (const a of areasRes) {
          if (a.area_id && a.name) areaMap[a.area_id] = a.name;
        }
      }

      const deviceAreaMap = {};
      if (Array.isArray(devicesRes)) {
        for (const d of devicesRes) {
          if (d.id && d.area_id && areaMap[d.area_id]) {
            deviceAreaMap[d.id] = areaMap[d.area_id];
          }
        }
      }

      this._aliases = {};
      this._excludedDefaultNames = {};
      if (aliasesRes && typeof aliasesRes === "object") {
        for (const [entId, val] of Object.entries(aliasesRes)) {
          if (Array.isArray(val)) {
            this._aliases[entId] = val;
            this._excludedDefaultNames[entId] = false;
          } else if (val && typeof val === "object") {
            this._aliases[entId] = Array.isArray(val.aliases) ? val.aliases : [];
            this._excludedDefaultNames[entId] = Boolean(val.exclude_default_name);
          }
        }
      }
      this._areas = {};
      if (Array.isArray(registryRes)) {
        for (const entry of registryRes) {
          if (!entry.entity_id) continue;
          if (!this._aliases[entry.entity_id]) {
            const rawAliases = (Array.isArray(entry.aliases_v2) && entry.aliases_v2.length > 0)
              ? entry.aliases_v2
              : (Array.isArray(entry.aliases) ? entry.aliases : []);

            if (rawAliases.length > 0) {
              this._aliases[entry.entity_id] = rawAliases
                .filter((a) => typeof a === "string" && a.trim().length > 0)
                .map((a) => this._sanitize(a))
                .filter(Boolean)
                .slice(0, 5);
            }
          }

          if (entry.area_id && areaMap[entry.area_id]) {
            this._areas[entry.entity_id] = areaMap[entry.area_id];
          } else if (entry.device_id && deviceAreaMap[entry.device_id]) {
            this._areas[entry.entity_id] = deviceAreaMap[entry.device_id];
          }
        }
      }
    } catch (err) {
      console.error("[AlexaAssistant] Failed to load data:", err);
    } finally {
      this._loading = false;
      this._render();
    }
  }

  async _toggleEntity(entityId, shouldExpose) {
    this._updating.add(entityId);
    this._render();
    try {
      await this._hass.callWS({
        type: "homeassistant/expose_entity",
        assistants: ["cloud.alexa"],
        entity_ids: [entityId],
        should_expose: shouldExpose,
      });

      if (!this._exposed[entityId]) {
        this._exposed[entityId] = {};
      }
      this._exposed[entityId]["cloud.alexa"] = shouldExpose;
    } catch (err) {
      console.error(`[AlexaAssistant] Failed to toggle ${entityId}:`, err);
      alert(`Error updating ${entityId}: ${err?.message || err}`);
    } finally {
      this._updating.delete(entityId);
      this._render();
    }
  }

  async _addAlias(entityId, aliasInput) {
    const rawVal = aliasInput?.value || "";
    const clean = this._sanitize(rawVal);
    if (!clean) {
      alert("Name must contain only letters, numbers, and spaces.");
      return;
    }

    const isDefaultExcluded = Boolean(this._excludedDefaultNames[entityId]);
    const current = this._aliases[entityId] ? [...this._aliases[entityId]] : [];
    const totalNames = (isDefaultExcluded ? 0 : 1) + current.length;

    if (totalNames >= 5) {
      alert("Maximum limit of 5 names reached.");
      return;
    }

    const entityObj = this._getAllValidEntities().find((e) => e.entity_id === entityId);
    const defaultName = entityObj ? entityObj.alexaName : "";

    const inputId = aliasInput?.id || `alias-input-${entityId.replace(/[^a-zA-Z0-9]/g, "_")}`;

    if (defaultName && clean.toLowerCase() === defaultName.toLowerCase()) {
      if (!isDefaultExcluded) {
        alert("This name is already registered.");
        return;
      }
      // Re-enable default name and clear field immediately
      this._clearedInputs.add(inputId);
      if (aliasInput) aliasInput.value = "";
      await this._saveAliases(entityId, current, false);
      const postInput = this.shadowRoot?.querySelector(`input[data-input-entity-id="${entityId}"]`);
      if (postInput) postInput.value = "";
      return;
    }

    if (current.some((a) => a.toLowerCase() === clean.toLowerCase())) {
      alert("This alias is already added.");
      return;
    }

    // Mark input as cleared immediately so re-render never restores the submitted alias
    this._clearedInputs.add(inputId);
    if (aliasInput) {
      aliasInput.value = "";
    }

    current.push(clean);
    await this._saveAliases(entityId, current, isDefaultExcluded);

    // Ensure input in DOM remains empty post-save
    const postInput = this.shadowRoot?.querySelector(`input[data-input-entity-id="${entityId}"]`);
    if (postInput) {
      postInput.value = "";
    }
  }

  async _removeAlias(entityId, aliasToRemove, isDefault) {
    const isDefaultExcluded = Boolean(this._excludedDefaultNames[entityId]);
    const current = this._aliases[entityId] ? [...this._aliases[entityId]] : [];
    const totalNames = (isDefaultExcluded ? 0 : 1) + current.length;

    if (totalNames <= 1) {
      alert("Cannot remove the only voice name.");
      return;
    }

    if (isDefault) {
      await this._saveAliases(entityId, current, true);
    } else {
      const updated = current.filter((a) => a !== aliasToRemove);
      await this._saveAliases(entityId, updated, isDefaultExcluded);
    }
  }

  async _restoreDefaultName(entityId) {
    const isDefaultExcluded = Boolean(this._excludedDefaultNames[entityId]);
    if (!isDefaultExcluded) return;

    const current = this._aliases[entityId] ? [...this._aliases[entityId]] : [];
    const totalNames = 1 + current.length;

    if (totalNames > 5) {
      alert("Maximum limit of 5 names reached.");
      return;
    }

    await this._saveAliases(entityId, current, false);
  }

  async _saveAliases(entityId, aliases, excludeDefault) {
    this._updating.add(entityId);
    this._render();
    try {
      await this._hass.callWS({
        type: "alexa_assistant/update_aliases",
        entity_id: entityId,
        aliases: aliases,
        exclude_default_name: Boolean(excludeDefault),
      });
      this._aliases[entityId] = aliases;
      this._excludedDefaultNames[entityId] = Boolean(excludeDefault);
    } catch (err) {
      console.error(`[AlexaAssistant] Failed to save aliases for ${entityId}:`, err);
      try {
        await this._hass.callWS({
          type: "config/entity_registry/update",
          entity_id: entityId,
          aliases: aliases,
        });
        this._aliases[entityId] = aliases;
      } catch (innerErr) {
        alert(`Error saving names: ${err?.message || err}`);
      }
    } finally {
      this._updating.delete(entityId);
      this._render();
    }
  }

  async _setScopeExposure(shouldExpose) {
    const filtered = this._getFilteredEntities();
    const entityIds = filtered.map((e) => e.entity_id);
    if (!entityIds.length) return;

    const actionText = shouldExpose ? "expose" : "hide";
    if (!confirm(`Are you sure you want to ${actionText} ${entityIds.length} device(s) to Alexa?`)) {
      return;
    }

    this._loading = true;
    this._render();
    try {
      await this._hass.callWS({
        type: "homeassistant/expose_entity",
        assistants: ["cloud.alexa"],
        entity_ids: entityIds,
        should_expose: shouldExpose,
      });

      for (const id of entityIds) {
        if (!this._exposed[id]) this._exposed[id] = {};
        this._exposed[id]["cloud.alexa"] = shouldExpose;
      }
    } catch (err) {
      console.error("[AlexaAssistant] Scope expose failed:", err);
      alert(`Error in batch update: ${err?.message || err}`);
    } finally {
      this._loading = false;
      this._render();
    }
  }

  _isExposed(entityId) {
    return Boolean(this._exposed[entityId]?.["cloud.alexa"]);
  }

  _getAllValidEntities() {
    if (!this._hass?.states) return [];
    const validDomains = new Set([
      "light", "switch", "cover", "climate", "media_player",
      "fan", "scene", "script", "sensor", "binary_sensor",
      "lock", "vacuum", "camera", "input_boolean"
    ]);

    return Object.entries(this._hass.states)
      .map(([id, stateObj]) => {
        const domain = id.split(".")[0];
        const rawName = stateObj.attributes.friendly_name || id;
        const sanitizedName = this._sanitize(rawName) || id;
        const aliases = this._aliases[id] || [];
        const isDefaultExcluded = Boolean(this._excludedDefaultNames[id]);
        const area = this._areas[id] || "No Area";
        return {
          entity_id: id,
          domain,
          name: rawName,
          alexaName: sanitizedName,
          area,
          aliases,
          isDefaultExcluded,
          state: stateObj.state,
          isExposed: this._isExposed(id),
        };
      })
      .filter((e) => validDomains.has(e.domain));
  }

  _getFilteredEntities() {
    const all = this._getAllValidEntities();

    const filtered = all.filter((e) => {
      // Area filter
      if (this._activeArea !== "all" && e.area !== this._activeArea) return false;
      // Domain filter
      if (this._activeDomain !== "all" && e.domain !== this._activeDomain) return false;
      // Exposure filter
      if (this._exposureFilter === "exposed" && !e.isExposed) return false;
      if (this._exposureFilter === "hidden" && e.isExposed) return false;

      // Text Search
      if (this._searchQuery.trim()) {
        const q = this._searchQuery.toLowerCase();
        const matchName = e.name.toLowerCase().includes(q);
        const matchAlexa = !e.isDefaultExcluded && e.alexaName.toLowerCase().includes(q);
        const matchId = e.entity_id.toLowerCase().includes(q);
        const matchArea = e.area.toLowerCase().includes(q);
        const matchDomain = e.domain.toLowerCase().includes(q);
        const matchAlias = e.aliases.some((a) => a.toLowerCase().includes(q));
        if (!matchName && !matchAlexa && !matchId && !matchArea && !matchDomain && !matchAlias) {
          return false;
        }
      }
      return true;
    });

    // Sort: Exposed entities first, then alphabetically by name
    return filtered.sort((a, b) => {
      if (a.isExposed === b.isExposed) {
        return a.name.localeCompare(b.name);
      }
      return a.isExposed ? -1 : 1;
    });
  }

  _render() {
    if (!this._hass) return;

    // Preserve scroll offsets across DOM re-renders (crucial for mobile touch UX)
    const prevScrollY = window.pageYOffset || document.documentElement.scrollTop || document.body.scrollTop || 0;
    const hostScrollTop = this.scrollTop || 0;
    const areaList = this.shadowRoot?.getElementById("areaFilterList");
    const domainList = this.shadowRoot?.getElementById("domainFilterList");
    const areaScrollLeft = areaList ? areaList.scrollLeft : 0;
    const domainScrollLeft = domainList ? domainList.scrollLeft : 0;

    const activeEl = this.shadowRoot ? this.shadowRoot.activeElement : null;
    const activeId = activeEl ? activeEl.id : null;
    const isCleared = activeId && this._clearedInputs.has(activeId);
    const activeVal = (activeEl && (activeEl.tagName === "INPUT" || activeEl.tagName === "TEXTAREA"))
      ? (isCleared ? "" : activeEl.value)
      : null;
    const activeSelStart = activeEl?.selectionStart;
    const activeSelEnd = activeEl?.selectionEnd;

    const allEntities = this._getAllValidEntities();
    const allRooms = Array.from(new Set(allEntities.map((e) => e.area))).sort();

    // Dynamically filter device types available in the currently selected Area
    const areaScopedEntities = this._activeArea === "all"
      ? allEntities
      : allEntities.filter((e) => e.area === this._activeArea);

    const availableDomains = Array.from(new Set(areaScopedEntities.map((e) => e.domain))).sort();

    // If the currently selected domain doesn't exist in the new area, reset domain to "all"
    if (this._activeDomain !== "all" && !availableDomains.includes(this._activeDomain)) {
      this._activeDomain = "all";
    }

    const filtered = this._getFilteredEntities();
    const totalExposedInView = filtered.filter((e) => e.isExposed).length;

    let filterTitle = "All Devices";
    if (this._activeArea !== "all" && this._activeDomain !== "all") {
      filterTitle = `${this._activeArea} • ${this._activeDomain.toUpperCase()}`;
    } else if (this._activeArea !== "all") {
      filterTitle = this._activeArea;
    } else if (this._activeDomain !== "all") {
      filterTitle = `All Areas • ${this._activeDomain.toUpperCase()}`;
    }

    const isDark = this._isDarkMode();
    const typeTextColor = isDark ? "#c084fc" : "#7e22ce";
    const typeBgColor = isDark ? "rgba(192, 132, 252, 0.18)" : "rgba(126, 34, 206, 0.10)";
    const typeBorderColor = isDark ? "rgba(192, 132, 252, 0.45)" : "rgba(126, 34, 206, 0.28)";

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          background-color: var(--primary-background-color, #0b0f19);
          color: var(--primary-text-color, #e2e8f0);
          font-family: var(--paper-font-body1_-_font-family, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif);
          min-height: 100vh;
          width: 100%;
          max-width: 100%;
          box-sizing: border-box;
          padding: 24px;
          overflow-x: hidden;
        }
        * { box-sizing: border-box; }
        .container {
          width: 100%;
          max-width: 1280px;
          margin: 0 auto;
          box-sizing: border-box;
        }
        @media (max-width: 768px) {
          :host {
            padding: 12px 10px;
          }
        }
        .header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          flex-wrap: wrap;
          gap: 12px;
          margin-bottom: 20px;
          padding-bottom: 16px;
          border-bottom: 1px solid var(--divider-color, rgba(255, 255, 255, 0.08));
        }
        .header-title {
          display: flex;
          align-items: center;
          flex-wrap: wrap;
          gap: 10px;
        }
        .header-title h1 {
          margin: 0;
          font-size: 22px;
          font-weight: 700;
          color: var(--primary-text-color, #111827);
        }
        /* High Contrast Theme Variables across Light and Dark */
        :host {
          --panel-primary-accent: var(--primary-color, #0284c7);
          --panel-primary-accent-contrast: var(--text-primary-color, #ffffff);
          --panel-pill-text: ${isDark ? "#38bdf8" : "#0369a1"};
          --panel-pill-bg: ${isDark ? "rgba(56, 189, 248, 0.15)" : "rgba(2, 132, 199, 0.12)"};
          --panel-pill-border: ${isDark ? "rgba(56, 189, 248, 0.35)" : "rgba(2, 132, 199, 0.28)"};
          --panel-type-text: ${typeTextColor};
          --panel-type-bg: ${typeBgColor};
          --panel-type-border: ${typeBorderColor};
          --panel-btn-primary-bg: #0369a1;
        }

        .badge {
          background-color: var(--panel-pill-bg);
          color: var(--panel-pill-text);
          border: 1px solid var(--panel-pill-border);
          padding: 4px 10px;
          border-radius: 12px;
          font-size: 12px;
          font-weight: 700;
        }
        .subtitle {
          color: var(--secondary-text-color, #94a3b8);
          font-size: 13px;
          margin-top: 4px;
        }
        .area-layout {
          display: grid;
          grid-template-columns: 280px minmax(0, 1fr);
          gap: 20px;
          width: 100%;
          min-width: 0;
        }
        @media (max-width: 768px) {
          .area-layout {
            display: flex;
            flex-direction: column;
            gap: 12px;
            width: 100%;
            min-width: 0;
          }
        }
        .area-sidebar {
          display: flex;
          flex-direction: column;
          gap: 16px;
          height: fit-content;
          min-width: 0;
        }
        .filter-card {
          background: var(--ha-card-background, var(--card-background-color, #131b2e));
          border: 1px solid var(--ha-card-border-color, var(--divider-color, #1e293b));
          border-radius: var(--ha-card-border-radius, 12px);
          padding: 14px;
          box-shadow: var(--ha-card-box-shadow, 0 2px 6px rgba(0,0,0,0.1));
          min-width: 0;
        }
        .filter-card-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding-bottom: 10px;
          margin-bottom: 10px;
          border-bottom: 1px solid var(--divider-color, rgba(255, 255, 255, 0.06));
        }
        .filter-card-title {
          font-size: 12px;
          font-weight: 700;
          color: var(--primary-text-color, #111827);
          text-transform: uppercase;
          letter-spacing: 0.06em;
          display: flex;
          align-items: center;
          gap: 7px;
        }
        .filter-card-title svg {
          width: 15px;
          height: 15px;
        }
        .filter-item-list {
          display: flex;
          flex-direction: column;
          gap: 4px;
          min-width: 0;
        }
        .area-item-btn {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 9px 12px;
          background: transparent;
          border: 1px solid transparent;
          border-radius: 8px;
          color: var(--primary-text-color, #e2e8f0);
          cursor: pointer;
          font-family: inherit;
          font-size: 13px;
          font-weight: 500;
          transition: all 0.15s ease;
          text-align: left;
          touch-action: manipulation;
          -webkit-tap-highlight-color: transparent;
        }
        .area-item-btn:hover {
          background: var(--secondary-background-color, rgba(125, 125, 125, 0.08));
        }
        .area-item-btn.active {
          background: var(--secondary-background-color, #1e293b);
          border-color: var(--panel-primary-accent);
          color: var(--panel-pill-text);
          font-weight: 700;
        }
        .area-badge {
          font-size: 11px;
          padding: 2px 7px;
          border-radius: 10px;
          background: var(--divider-color, rgba(125, 125, 125, 0.12));
          color: var(--secondary-text-color, #94a3b8);
          flex-shrink: 0;
        }
        @media (max-width: 768px) {
          .area-sidebar {
            gap: 10px;
          }
          .filter-card {
            padding: 10px 12px;
          }
          .filter-card-header {
            padding-bottom: 6px;
            margin-bottom: 6px;
          }
          .filter-item-list {
            flex-direction: row;
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
            gap: 6px;
            padding-bottom: 4px;
            scrollbar-width: thin;
          }
          .filter-item-list::-webkit-scrollbar {
            height: 4px;
          }
          .filter-item-list::-webkit-scrollbar-thumb {
            background: var(--divider-color, rgba(255, 255, 255, 0.2));
            border-radius: 4px;
          }
          .area-item-btn {
            flex-shrink: 0;
            white-space: nowrap;
            padding: 6px 12px;
            font-size: 12px;
            border-radius: 16px;
            background: var(--ha-card-background, rgba(125, 125, 125, 0.08));
            border: 1px solid var(--divider-color, rgba(125, 125, 125, 0.15));
            gap: 6px;
          }
          .area-item-btn.active {
            background: var(--panel-pill-bg, rgba(56, 189, 248, 0.18));
            border-color: var(--panel-primary-accent, #0284c7);
            color: var(--panel-pill-text, #38bdf8);
          }
        }
        .room-header-card {
          background: var(--ha-card-background, var(--card-background-color, #131b2e));
          border: 1px solid var(--ha-card-border-color, var(--divider-color, #334155));
          border-radius: var(--ha-card-border-radius, 12px);
          padding: 16px 20px;
          margin-bottom: 16px;
          display: flex;
          justify-content: space-between;
          align-items: center;
          flex-wrap: wrap;
          gap: 12px;
          box-shadow: var(--ha-card-box-shadow, 0 2px 6px rgba(0,0,0,0.1));
          min-width: 0;
        }
        .room-header-card h2 {
          margin: 0;
          font-size: 19px;
          font-weight: 700;
          color: var(--primary-text-color, #111827);
          word-break: break-word;
        }
        .room-header-card p {
          margin: 4px 0 0 0;
          font-size: 13px;
          color: var(--secondary-text-color, #94a3b8);
        }
        .btn-sm {
          padding: 7px 14px;
          border-radius: 6px;
          font-size: 12px;
          font-weight: 600;
          cursor: pointer;
          border: 1px solid var(--divider-color, #334155);
          background: var(--card-background-color, #1e293b);
          color: var(--primary-text-color, #e2e8f0);
          transition: all 0.15s;
          touch-action: manipulation;
          -webkit-tap-highlight-color: transparent;
        }
        .btn-sm:hover {
          background: var(--secondary-background-color, #334155);
        }
        .btn-sm-primary {
          background: var(--panel-btn-primary-bg);
          border-color: var(--panel-btn-primary-bg);
          color: var(--panel-primary-accent-contrast);
        }
        .btn-sm-primary:hover {
          opacity: 0.9;
        }
        .room-filter-row {
          display: flex;
          gap: 12px;
          margin-bottom: 16px;
          align-items: center;
          flex-wrap: wrap;
          width: 100%;
          min-width: 0;
        }
        .room-search-bar {
          flex: 1 1 240px;
          min-width: 0;
          position: relative;
          display: flex;
          align-items: center;
        }
        .room-search-input {
          width: 100%;
          background: var(--ha-card-background, var(--card-background-color, #131b2e));
          border: 1px solid var(--divider-color, #1e293b);
          border-radius: 8px;
          color: var(--primary-text-color, #111827);
          padding: 9px 14px 9px 36px;
          font-size: 13px;
          outline: none;
          transition: border-color 0.2s;
          box-sizing: border-box;
        }
        .room-search-input:focus {
          border-color: var(--primary-color, #38bdf8);
        }
        .room-search-icon {
          position: absolute;
          left: 11px;
          width: 15px;
          height: 15px;
          fill: var(--secondary-text-color, #64748b);
          pointer-events: none;
        }
        .room-exposure-toggle-group {
          display: inline-flex;
          background: var(--ha-card-background, var(--card-background-color, #131b2e));
          border: 1px solid var(--divider-color, #1e293b);
          border-radius: 8px;
          padding: 3px;
          gap: 3px;
          flex-shrink: 0;
        }
        .room-exposure-btn {
          padding: 6px 14px;
          background: transparent;
          border: none;
          border-radius: 6px;
          color: var(--secondary-text-color, #94a3b8);
          font-size: 13px;
          font-weight: 500;
          font-family: inherit;
          cursor: pointer;
          display: inline-flex;
          align-items: center;
          gap: 6px;
          transition: all 0.15s ease;
          touch-action: manipulation;
          -webkit-tap-highlight-color: transparent;
        }
        .room-exposure-btn:hover {
          color: var(--primary-text-color, #111827);
        }
        .room-exposure-btn.active {
          background: var(--secondary-background-color, #1e293b);
          color: var(--panel-pill-text);
          font-weight: 700;
        }
        @media (max-width: 600px) {
          .room-header-card {
            padding: 12px 14px;
          }
          .room-filter-row {
            flex-direction: column;
            align-items: stretch;
            gap: 10px;
          }
          .room-search-bar {
            width: 100%;
            flex: none;
          }
          .room-exposure-toggle-group {
            width: 100%;
            display: flex;
          }
          .room-exposure-btn {
            flex: 1;
            justify-content: center;
            padding: 8px 10px;
            font-size: 12px;
          }
        }
        .m3-card {
          background: var(--ha-card-background, var(--card-background-color, #131b2e));
          border: 1px solid var(--ha-card-border-color, var(--divider-color, #1e293b));
          border-radius: var(--ha-card-border-radius, 12px);
          padding: 16px;
          transition: all 0.2s ease;
          box-shadow: var(--ha-card-box-shadow, 0 1px 3px rgba(0,0,0,0.08));
          width: 100%;
          min-width: 0;
          overflow: hidden;
          box-sizing: border-box;
        }
        .m3-card.exposed {
          border-left: 5px solid var(--primary-color, #00e5ff);
        }
        .m3-card.hidden {
          border-left: 5px solid var(--secondary-text-color, #475569);
          opacity: 0.88;
        }
        .card-main-row {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          gap: 12px;
          width: 100%;
          min-width: 0;
        }
        .card-info-col {
          flex: 1 1 auto;
          min-width: 0;
          overflow: hidden;
        }
        .card-badges-row {
          display: flex;
          flex-wrap: wrap;
          align-items: center;
          gap: 6px;
          margin-bottom: 6px;
        }
        .entity-title {
          font-weight: 600;
          font-size: 15px;
          color: var(--primary-text-color, #111827);
          word-break: break-word;
          overflow-wrap: anywhere;
          line-height: 1.35;
        }
        .entity-id-sub {
          font-size: 11px;
          font-family: monospace;
          color: var(--secondary-text-color, #64748b);
          margin-top: 3px;
          word-break: break-all;
          overflow-wrap: anywhere;
        }
        .domain-tag {
          font-size: 10px;
          text-transform: uppercase;
          background: var(--panel-type-bg);
          border: 1px solid var(--panel-type-border);
          color: var(--panel-type-text);
          padding: 2px 7px;
          border-radius: 4px;
          font-weight: 700;
          letter-spacing: 0.04em;
          flex-shrink: 0;
        }
        .area-tag {
          font-size: 11px;
          color: var(--panel-pill-text);
          background: var(--panel-pill-bg);
          border: 1px solid var(--panel-pill-border);
          padding: 2px 8px;
          border-radius: 10px;
          font-weight: 600;
          flex-shrink: 0;
        }
        .card-toggle-col {
          display: flex;
          align-items: center;
          gap: 8px;
          flex-shrink: 0;
          margin-top: 2px;
        }
        .status-label {
          font-size: 12px;
          font-weight: 600;
        }
        .status-label.exposed {
          color: #10b981;
        }
        .status-label.hidden {
          color: #64748b;
        }
        /* Mobile Touch-proof Toggle Switch */
        .switch {
          position: relative;
          display: inline-block;
          width: 44px;
          height: 24px;
          touch-action: manipulation;
          -webkit-tap-highlight-color: transparent;
        }
        .switch input {
          position: absolute;
          top: 0;
          left: 0;
          width: 100%;
          height: 100%;
          margin: 0;
          opacity: 0;
          cursor: pointer;
          z-index: 2;
          -webkit-appearance: none;
          appearance: none;
          touch-action: manipulation;
        }
        .slider {
          position: absolute;
          pointer-events: none;
          top: 0; left: 0; right: 0; bottom: 0;
          background-color: var(--secondary-text-color, #334155);
          transition: 0.25s;
          border-radius: 24px;
        }
        .slider:before {
          position: absolute;
          content: "";
          height: 18px;
          width: 18px;
          left: 3px;
          bottom: 3px;
          background-color: white;
          transition: 0.25s;
          border-radius: 50%;
        }
        input:checked + .slider {
          background-color: var(--primary-color, #00e5ff);
        }
        input:checked + .slider:before {
          transform: translateX(20px);
        }

        /* Voice Aliases row */
        .alias-container {
          margin-top: 12px;
          padding-top: 10px;
          border-top: 1px solid var(--divider-color, rgba(255, 255, 255, 0.06));
          display: flex;
          flex-wrap: wrap;
          align-items: center;
          gap: 8px;
          width: 100%;
          min-width: 0;
        }
        .alias-default-chip {
          background: var(--panel-pill-bg);
          border: 1px solid var(--panel-pill-border);
          color: var(--panel-pill-text);
          font-size: 12px;
          padding: 4px 8px 4px 10px;
          border-radius: 20px;
          display: inline-flex;
          align-items: center;
          gap: 6px;
          font-weight: 700;
          max-width: 100%;
          box-sizing: border-box;
          touch-action: manipulation;
        }
        .alias-chip {
          background: var(--secondary-background-color, rgba(125, 125, 125, 0.1));
          border: 1px solid var(--divider-color, rgba(125, 125, 125, 0.2));
          color: var(--primary-text-color, #e2e8f0);
          font-size: 12px;
          padding: 4px 8px 4px 10px;
          border-radius: 20px;
          display: inline-flex;
          align-items: center;
          gap: 6px;
          max-width: 100%;
          box-sizing: border-box;
          touch-action: manipulation;
        }
        .alias-chip-text {
          max-width: 180px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        @media (max-width: 480px) {
          .alias-chip-text {
            max-width: 120px;
          }
        }
        .alias-chip-del {
          background: none;
          border: none;
          color: var(--secondary-text-color, #94a3b8);
          cursor: pointer;
          font-size: 16px;
          line-height: 1;
          padding: 4px;
          min-width: 24px;
          min-height: 24px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          border-radius: 50%;
          touch-action: manipulation;
          -webkit-tap-highlight-color: transparent;
        }
        .alias-chip-del:hover {
          color: var(--error-color, #f87171);
          background: rgba(248, 113, 113, 0.1);
        }
        .alias-default-chip .alias-chip-del {
          color: var(--panel-pill-text);
          opacity: 0.7;
        }
        .alias-default-chip .alias-chip-del:hover {
          color: var(--error-color, #f87171);
          opacity: 1;
        }
        .alias-add-original-btn {
          background: rgba(0, 229, 255, 0.08);
          border: 1px dashed var(--panel-pill-border, rgba(0, 229, 255, 0.4));
          color: var(--panel-pill-text, #00e5ff);
          font-size: 11px;
          font-weight: 600;
          padding: 5px 10px;
          min-height: 28px;
          border-radius: 20px;
          cursor: pointer;
          display: inline-flex;
          align-items: center;
          transition: all 0.15s ease;
          touch-action: manipulation;
          -webkit-tap-highlight-color: transparent;
        }
        .alias-add-original-btn:hover {
          background: var(--panel-pill-bg, rgba(0, 229, 255, 0.18));
          border-style: solid;
        }
        .alias-input-group {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          max-width: 100%;
        }
        @media (max-width: 480px) {
          .alias-input-group {
            width: 100%;
          }
        }
        .grid-inline-input {
          background: var(--primary-background-color, #ffffff);
          border: 1px solid var(--divider-color, #e2e8f0);
          color: var(--primary-text-color, #111827);
          font-size: 12px;
          padding: 6px 10px;
          height: 32px;
          border-radius: 6px;
          outline: none;
          width: 140px;
          box-sizing: border-box;
        }
        .grid-inline-input:focus {
          border-color: var(--primary-color, #38bdf8);
        }
        @media (max-width: 480px) {
          .grid-inline-input {
            flex: 1;
            width: auto;
            min-width: 100px;
          }
        }
        .alias-btn-check {
          background: var(--panel-btn-primary-bg);
          border: none;
          border-radius: 6px;
          color: var(--panel-primary-accent-contrast);
          cursor: pointer;
          width: 32px;
          height: 32px;
          min-width: 32px;
          min-height: 32px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          transition: opacity 0.15s;
          touch-action: manipulation;
          -webkit-tap-highlight-color: transparent;
        }
        .alias-btn-check:hover {
          opacity: 0.9;
        }
      </style>

      <div class="container">
        <!-- Header -->
        <div class="header">
          <div>
            <div class="header-title">
              <h1>Alexa Assistant</h1>
              <span class="badge">${allEntities.filter((e) => e.isExposed).length} exposed</span>
            </div>
            <div class="subtitle">Spatial device management &amp; voice aliases for Amazon Alexa</div>
          </div>
          <div>
            <button class="btn-sm" id="btnRefresh">Refresh</button>
          </div>
        </div>

        <div class="area-layout">
          <!-- Sidebar: 2 Distinct Visual Sections (Area & Device Type) -->
          <div class="area-sidebar">
            <!-- Distinct Card 1: Area Filter -->
            <div class="filter-card">
              <div class="filter-card-header">
                <div class="filter-card-title">
                  <svg style="fill:#38bdf8;" viewBox="0 0 24 24"><path d="M10,20V14H14V20H19V12H22L12,3L2,12H5V20H10Z"/></svg>
                  <span>Areas</span>
                </div>
                <span class="area-badge">${allRooms.length} rooms</span>
              </div>
              <div class="filter-item-list" id="areaFilterList">
                <button class="area-item-btn ${this._activeArea === "all" ? "active" : ""}" data-area-btn="all">
                  <span>All Areas</span>
                  <span class="area-badge">${allEntities.filter((e) => e.isExposed).length}/${allEntities.length}</span>
                </button>
                ${allRooms.map((room) => {
                  const count = allEntities.filter((e) => e.area === room && e.isExposed).length;
                  const total = allEntities.filter((e) => e.area === room).length;
                  return `
                    <button class="area-item-btn ${room === this._activeArea ? "active" : ""}" data-area-btn="${room}">
                      <span>${room}</span>
                      <span class="area-badge">${count}/${total}</span>
                    </button>
                  `;
                }).join("")}
              </div>
            </div>

            <!-- Distinct Card 2: Device Type Filter (Filtered by selected Area) -->
            <div class="filter-card">
              <div class="filter-card-header">
                <div class="filter-card-title">
                  <svg style="fill:#a855f7;" viewBox="0 0 24 24"><path d="M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2M12,4A8,8 0 0,1 20,12A8,8 0 0,1 12,20A8,8 0 0,1 4,12A8,8 0 0,1 12,4M12,6A6,6 0 0,0 6,12A6,6 0 0,0 12,18A6,6 0 0,0 18,12A6,6 0 0,0 12,6M12,8A4,4 0 0,1 16,12A4,4 0 0,1 12,16A4,4 0 0,1 8,12A4,4 0 0,1 12,8Z"/></svg>
                  <span>Device Types</span>
                </div>
                <span class="area-badge">${availableDomains.length} types</span>
              </div>
              <div class="filter-item-list" id="domainFilterList">
                <button class="area-item-btn ${this._activeDomain === "all" ? "active" : ""}" data-domain-btn="all">
                  <span>All Types</span>
                  <span class="area-badge">${areaScopedEntities.filter((e) => e.isExposed).length}/${areaScopedEntities.length}</span>
                </button>
                ${availableDomains.map((dom) => {
                  const count = areaScopedEntities.filter((e) => e.domain === dom && e.isExposed).length;
                  const total = areaScopedEntities.filter((e) => e.domain === dom).length;
                  return `
                    <button class="area-item-btn ${dom === this._activeDomain ? "active" : ""}" data-domain-btn="${dom}">
                      <span style="text-transform:capitalize;">${dom}</span>
                      <span class="area-badge">${count}/${total}</span>
                    </button>
                  `;
                }).join("")}
              </div>
            </div>
          </div>

          <!-- Main Devices Explorer -->
          <div style="min-width:0;">
            <!-- Header Card with Expose All / Hide All for current scope -->
            <div class="room-header-card">
              <div>
                <h2>${filterTitle}</h2>
                <p>${totalExposedInView} of ${filtered.length} devices currently exposed to Alexa</p>
              </div>
              <div style="display:flex; gap:10px; align-items:center;">
                <button class="btn-sm btn-sm-primary" id="btnExposeAll">Expose All</button>
                <button class="btn-sm" id="btnHideAll">Hide All</button>
              </div>
            </div>

            <!-- Search field + Exposure filter row -->
            <div class="room-filter-row">
              <div class="room-search-bar">
                <svg class="room-search-icon" viewBox="0 0 24 24"><path d="M9.5,3A6.5,6.5 0 0,1 16,9.5C16,11.11 15.41,12.59 14.44,13.73L14.71,14H15.5L20.5,19L19,20.5L14,15.5V14.71L13.73,14.44C12.59,15.41 11.11,16 9.5,16A6.5,6.5 0 0,1 3,9.5A6.5,6.5 0 0,1 9.5,3M9.5,5C7,5 5,7 5,9.5C5,12 7,14 9.5,14C12,14 14,12 14,9.5C14,7 12,5 9.5,5Z"/></svg>
                <input type="text"
                  id="searchInput"
                  class="room-search-input"
                  placeholder="Search filtered devices by name, Alexa phrase, entity ID or alias..."
                  value="${this._searchQuery}">
              </div>

              <!-- Filter: All / Exposed / Hidden -->
              <div class="room-exposure-toggle-group">
                <button class="room-exposure-btn ${this._exposureFilter === "all" ? "active" : ""}" data-exposure="all">
                  All
                </button>
                <button class="room-exposure-btn ${this._exposureFilter === "exposed" ? "active" : ""}" data-exposure="exposed">
                  <span style="display:inline-block; width:6px; height:6px; border-radius:50%; background:#10b981;"></span>
                  Exposed
                </button>
                <button class="room-exposure-btn ${this._exposureFilter === "hidden" ? "active" : ""}" data-exposure="hidden">
                  <span style="display:inline-block; width:6px; height:6px; border-radius:50%; background:#64748b;"></span>
                  Hidden
                </button>
              </div>
            </div>

            <!-- Device list -->
            ${filtered.length === 0 ? `
              <div style="text-align:center; padding:48px; background:#131b2e; border:1px solid #1e293b; border-radius:12px; color:#94a3b8;">
                <p style="font-size:15px; font-weight:600; margin:0;">No devices match the active filters or search</p>
                <p style="font-size:13px; margin-top:4px;">Try clearing the search query or selecting "All" in the filters.</p>
              </div>
            ` : `
              <div style="display:flex; flex-direction:column; gap:12px; min-width:0;">
                ${filtered.map((e) => {
                  const cleanName = e.alexaName;
                  const inputId = `alias-input-${e.entity_id.replace(/[^a-zA-Z0-9]/g, "_")}`;
                  return `
                    <div class="m3-card ${e.isExposed ? "exposed" : "hidden"}">
                      <div class="card-main-row">
                        <div class="card-info-col">
                          <div class="card-badges-row">
                            <span class="area-tag">${e.area}</span>
                            <span class="domain-tag">${e.domain}</span>
                          </div>
                          <div class="entity-title">${e.name}</div>
                          <div class="entity-id-sub">${e.entity_id}</div>
                        </div>

                        <div class="card-toggle-col">
                          <span class="status-label ${e.isExposed ? "exposed" : "hidden"}">${e.isExposed ? "Exposed" : "Hidden"}</span>
                          <label class="switch">
                            <input type="checkbox" data-entity-id="${e.entity_id}" ${e.isExposed ? "checked" : ""} ${this._updating.has(e.entity_id) ? "disabled" : ""}>
                            <span class="slider"></span>
                          </label>
                        </div>
                      </div>

                      <!-- ALIAS MANAGER (ONLY WHEN EXPOSED) -->
                      ${e.isExposed ? `
                        <div class="alias-container">
                          <!-- Microphone icon indicator -->
                          <span style="display:inline-flex; align-items:center; color:#00e5ff; flex-shrink:0;" title="Voice Names (Alexa)">
                            <svg style="width:16px;height:16px;fill:currentColor;" viewBox="0 0 24 24"><path d="M12 2A3 3 0 0 0 9 5V11A3 3 0 0 0 12 14A3 3 0 0 0 15 11V5A3 3 0 0 0 12 2M19 11C19 14.53 16.39 17.44 13 17.93V21H11V17.93C7.61 17.44 5 14.53 5 11H7A5 5 0 0 0 12 16A5 5 0 0 0 17 11H19Z"/></svg>
                          </span>

                          <!-- 1st Item: Clean Entity Name (if not excluded) -->
                          ${!e.isDefaultExcluded ? `
                            <span class="alias-default-chip" title="Original entity name">
                              <span class="alias-chip-text">${cleanName}</span>
                              <button class="alias-chip-del" title="Remove name" data-entity-id="${e.entity_id}" data-is-default="true">×</button>
                            </span>
                          ` : `
                            <button class="alias-add-original-btn" title="Add &quot;${cleanName}&quot; as primary discovery name" data-restore-entity-id="${e.entity_id}">
                              <svg style="width:12px;height:12px;fill:currentColor;margin-right:4px;" viewBox="0 0 24 24"><path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/></svg>
                              Add name to aliases
                            </button>
                          `}

                          <!-- Configured secondary aliases -->
                          ${e.aliases.map((alias) => `
                            <span class="alias-chip">
                              <span class="alias-chip-text">${alias}</span>
                              <button class="alias-chip-del" title="Remove alias" data-entity-id="${e.entity_id}" data-alias="${alias}">×</button>
                            </span>
                          `).join("")}

                          <!-- Add alias input with Enter + Check Mark button -->
                          ${((e.isDefaultExcluded ? 0 : 1) + e.aliases.length) < 5 ? `
                            <div class="alias-input-group">
                              <input type="text"
                                id="${inputId}"
                                class="grid-inline-input"
                                placeholder="+ Add alias..."
                                data-input-entity-id="${e.entity_id}">
                              <button class="alias-btn-check"
                                title="Add alias"
                                data-btn-add-entity-id="${e.entity_id}">
                                <svg style="width:14px;height:14px;fill:currentColor;" viewBox="0 0 24 24"><path d="M21,7L9,19L3.5,13.5L4.91,12.09L9,16.17L19.59,5.59L21,7Z"/></svg>
                              </button>
                            </div>
                          ` : `
                            <span style="font-size:11px; color:#f59e0b; font-style:italic;">${((e.isDefaultExcluded ? 0 : 1) + e.aliases.length)}/5 reached</span>
                          `}
                        </div>
                      ` : ""}
                    </div>
                  `;
                }).join("")}
              </div>
            `}
          </div>
        </div>
      </div>
    `;

    this._bindEvents();

    if (activeId && activeId !== "searchInput") {
      const restored = this.shadowRoot.getElementById(activeId);
      if (restored) {
        if (this._clearedInputs.has(activeId)) {
          restored.value = "";
          this._clearedInputs.delete(activeId);
        } else if (activeVal !== null && restored.value !== activeVal) {
          restored.value = activeVal;
        }
        restored.focus();
        if (typeof activeSelStart === "number" && typeof activeSelEnd === "number") {
          restored.setSelectionRange(activeSelStart, activeSelEnd);
        }
      }
    }

    // Restore scroll positions so mobile screen does not jump to top on tap/toggle
    requestAnimationFrame(() => {
      if (typeof prevScrollY === "number" && prevScrollY > 0) {
        window.scrollTo(0, prevScrollY);
      }
      if (typeof hostScrollTop === "number" && hostScrollTop > 0) {
        this.scrollTop = hostScrollTop;
      }
      const newAreaList = this.shadowRoot?.getElementById("areaFilterList");
      if (newAreaList && areaScrollLeft > 0) {
        newAreaList.scrollLeft = areaScrollLeft;
      }
      const newDomainList = this.shadowRoot?.getElementById("domainFilterList");
      if (newDomainList && domainScrollLeft > 0) {
        newDomainList.scrollLeft = domainScrollLeft;
      }
    });
  }

  _bindEvents() {
    const searchInput = this.shadowRoot.getElementById("searchInput");
    if (searchInput) {
      searchInput.addEventListener("input", (e) => {
        this._searchQuery = e.target.value;
        this._render();
        const nextInput = this.shadowRoot.getElementById("searchInput");
        if (nextInput) {
          nextInput.focus();
          nextInput.setSelectionRange(nextInput.value.length, nextInput.value.length);
        }
      });
    }

    const btnRefresh = this.shadowRoot.getElementById("btnRefresh");
    if (btnRefresh) {
      btnRefresh.addEventListener("click", () => this._loadData());
    }

    const btnExposeAll = this.shadowRoot.getElementById("btnExposeAll");
    if (btnExposeAll) {
      btnExposeAll.addEventListener("click", () => this._setScopeExposure(true));
    }

    const btnHideAll = this.shadowRoot.getElementById("btnHideAll");
    if (btnHideAll) {
      btnHideAll.addEventListener("click", () => this._setScopeExposure(false));
    }

    // Area buttons
    const areaBtns = this.shadowRoot.querySelectorAll("button[data-area-btn]");
    areaBtns.forEach((btn) => {
      btn.addEventListener("click", () => {
        this._activeArea = btn.getAttribute("data-area-btn");
        this._render();
      });
    });

    // Domain buttons
    const domainBtns = this.shadowRoot.querySelectorAll("button[data-domain-btn]");
    domainBtns.forEach((btn) => {
      btn.addEventListener("click", () => {
        this._activeDomain = btn.getAttribute("data-domain-btn");
        this._render();
      });
    });

    // Exposure filter buttons
    const exposureBtns = this.shadowRoot.querySelectorAll("button[data-exposure]");
    exposureBtns.forEach((btn) => {
      btn.addEventListener("click", () => {
        this._exposureFilter = btn.getAttribute("data-exposure");
        this._render();
      });
    });

    // Toggle switch
    const checkboxes = this.shadowRoot.querySelectorAll('input[type="checkbox"][data-entity-id]');
    checkboxes.forEach((cb) => {
      cb.addEventListener("change", (e) => {
        const id = e.target.getAttribute("data-entity-id");
        this._toggleEntity(id, e.target.checked);
      });
    });

    // Restore default name button
    const restoreButtons = this.shadowRoot.querySelectorAll("button[data-restore-entity-id]");
    restoreButtons.forEach((btn) => {
      btn.addEventListener("click", () => {
        const entityId = btn.getAttribute("data-restore-entity-id");
        this._restoreDefaultName(entityId);
      });
    });

    // Remove alias buttons
    const removeButtons = this.shadowRoot.querySelectorAll("button.alias-chip-del");
    removeButtons.forEach((btn) => {
      btn.addEventListener("click", () => {
        const entityId = btn.getAttribute("data-entity-id");
        const isDefault = btn.getAttribute("data-is-default") === "true";
        const alias = btn.getAttribute("data-alias");
        this._removeAlias(entityId, alias, isDefault);
      });
    });

    // Add alias buttons (checkmark)
    const addButtons = this.shadowRoot.querySelectorAll("button[data-btn-add-entity-id]");
    addButtons.forEach((btn) => {
      btn.addEventListener("click", () => {
        const entityId = btn.getAttribute("data-btn-add-entity-id");
        const input = this.shadowRoot.querySelector(`input[data-input-entity-id="${entityId}"]`);
        this._addAlias(entityId, input);
      });
    });

    // Add alias enter key
    const addInputs = this.shadowRoot.querySelectorAll("input[data-input-entity-id]");
    addInputs.forEach((inp) => {
      inp.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          const entityId = inp.getAttribute("data-input-entity-id");
          this._addAlias(entityId, inp);
        }
      });
    });
  }
}

if (!customElements.get("alexa-assistant-panel")) {
  customElements.define("alexa-assistant-panel", AlexaAssistantPanel);
}
