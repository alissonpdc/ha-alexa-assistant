# Alexa Native Expose

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Enable Home Assistant's native **Voice Assistants > Expose** UI for manual/self-hosted Amazon Alexa Smart Home skills.

---

## The Problem

When using the official self-hosted/manual Alexa Smart Home integration (`alexa: smart_home:` via AWS Lambda), Home Assistant disables or ignores the built-in UI toggles under **Settings > Voice Assistants > Expose**, requiring users to maintain static entity filter lists in `configuration.yaml` and restart or reload every time.

## The Solution

**Alexa Native Expose** connects the manual Alexa discovery pipeline to Home Assistant's core `exposed_entities` manager:

- **Native UI Toggle**: Activates the Alexa toggle column in **Settings > Voice Assistants > Expose**.
- **Real-Time Control**: Expose or hide lights, switches, scenes, and sensors with a single click.
- **Zero Configuration**: No YAML filters required.

---

## Installation via HACS

1. Open **HACS** in your Home Assistant sidebar.
2. Click the three dots in the top right corner and choose **Custom repositories**.
3. Add repository:
   - **Repository**: `https://github.com/alissonpdc/ha-alexa-native-expose`
   - **Type**: `Integration`
4. Click **Add** and search for **Alexa Native Expose**.
5. Click **Download** and restart Home Assistant.

---

## Configuration

1. In Home Assistant, go to **Settings > Devices & Services**.
2. Click **Add Integration** and search for **Alexa Native Expose**.
3. Confirm the setup.
4. Navigate to **Settings > Voice Assistants > Expose** to toggle entities for Alexa directly.
5. In your `configuration.yaml`, ensure you have:
   ```yaml
   alexa:
     smart_home:
   ```

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
