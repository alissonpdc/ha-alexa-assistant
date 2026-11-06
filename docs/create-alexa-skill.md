# Complete Guide: Manual Alexa Smart Home Skill & AWS Setup

This guide documents the end-to-end setup of a self-hosted Amazon Alexa Smart Home Skill for Home Assistant without relying on Nabu Casa, including the AWS Lambda backend, the API Gateway port 443 reverse proxy, and solutions to all common OAuth errors.

---

## Architecture Overview

```
[ Echo Device / Alexa App ]
           │
           │ (1) Directives: TurnOn, TurnOff, Discover
           ▼
[ AWS Lambda (us-east-1) ]
           │
           │ (HTTPS) Direct call to /api/alexa/smart_home
           ▼
[ Home Assistant (https://your-domain:port) ]

─────────────────────────────────────────────────────────────
OAuth Account Linking Handshake:

[ User Mobile Phone ] ──(1) Browser Login──▶ [ Home Assistant (Direct URL) ]
                                                        │
[ Alexa Backend Server ] ◀──(2) Code Redirect──────────┘
           │
           │ (3) Token Exchange: POST /auth/token (Strict Port 443 Requirement)
           ▼
[ AWS API Gateway (Port 443) ]
           │
           │ (4) Reverse Proxy to Custom Port
           ▼
[ Home Assistant (/auth/token) ]
```

---

## Prerequisites

1. **Home Assistant with Public HTTPS**:
   - A valid public domain (e.g., DuckDNS or custom domain) with a trusted SSL/TLS certificate (Let's Encrypt).
   - Tested and verified over HTTPS (e.g., `https://your-ha.duckdns.org:8123` or custom port).
2. **Amazon Developer Account**:
   - Access to [developer.amazon.com](https://developer.amazon.com/alexa/console/ask) using the **same Amazon account** configured on your Echo devices.
3. **AWS Account & CLI**:
   - Access to AWS Console or configured AWS CLI (`aws sso login` or IAM credentials).

---

## Step 1: Configure Home Assistant

Add the Alexa Smart Home integration to your `/root/config/configuration.yaml`:

```yaml
alexa:
  smart_home:
```

Validate and restart Home Assistant:
```bash
ha core check
ha core restart
```

Verify that the smart home endpoint responds (must return JSON with endpoints):
```bash
curl -s -X POST https://your-ha-domain:port/api/alexa/smart_home \
  -H "Authorization: Bearer <LONG_LIVED_ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"directive":{"header":{"namespace":"Alexa.Discovery","name":"Discover","payloadVersion":"3","messageId":"1"},"payload":{"scope":{"type":"BearerToken","token":"<LONG_LIVED_ACCESS_TOKEN>"}}}}'
```

---

## Step 2: Provision AWS IAM Role & Lambda Function

> [!IMPORTANT]
> **Region Requirement**: For North and South America (including Brazil / Portuguese BR), Amazon Alexa **strictly requires** the Lambda function to be hosted in **`us-east-1` (N. Virginia)**. Endpoints in `sa-east-1` (São Paulo) or other regions will be rejected by the Alexa Developer Console.

### 2.1 Create IAM Role

```bash
aws iam create-role \
  --role-name HomeAssistant-Alexa-Role \
  --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}' \
  --description "Role for Home Assistant Alexa Smart Home Skill Lambda"

aws iam attach-role-policy \
  --role-name HomeAssistant-Alexa-Role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
```

### 2.2 Lambda Function Code (`lambda_function.py`)

Create `lambda_function.py`:

```python
"""
Alexa Smart Home Skill Adapter for Home Assistant
"""
import os
import json
import logging
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import ssl
from typing import Any

_debug = bool(os.environ.get('DEBUG', False))
_logger = logging.getLogger('HomeAssistant-SmartHome')
_logger.setLevel(logging.DEBUG if _debug else logging.INFO)

def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Handle incoming Alexa directive and forward to Home Assistant."""
    _logger.debug('Event: %s', event)

    base_url = os.environ.get('BASE_URL', '').rstrip('/')
    assert base_url, 'Please set BASE_URL environment variable'

    # Extract OAuth bearer token passed by Alexa directive
    token = None
    try:
        token = event['directive']['payload']['scope']['token']
    except (KeyError, TypeError):
        pass

    if not token:
        try:
            token = event['directive']['endpoint']['scope']['token']
        except (KeyError, TypeError):
            pass

    if not token:
        token = os.environ.get('LONG_LIVED_ACCESS_TOKEN')

    assert token is not None, 'Access token not found in event payload or environment variables'

    endpoint = f"{base_url}/api/alexa/smart_home"
    data = json.dumps(event).encode('utf-8')
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }

    req = Request(endpoint, data=data, headers=headers, method='POST')
    ctx = ssl.create_default_context()

    try:
        with urlopen(req, context=ctx, timeout=10) as response:
            res_body = response.read().decode('utf-8')
            return json.loads(res_body)
    except HTTPError as e:
        error_body = e.read().decode('utf-8')
        _logger.error('Home Assistant returned status %s: %s', e.code, error_body)
        err_type = 'INVALID_AUTHORIZATION_CREDENTIAL' if e.code in (401, 403) else 'INTERNAL_ERROR'
        return {
            'event': {
                'payload': {
                    'type': err_type,
                    'message': error_body
                }
            }
        }
    except Exception as e:
        _logger.exception('Error connecting to Home Assistant')
        msg_id = event.get('directive', {}).get('header', {}).get('messageId', 'unknown')
        return {
            'event': {
                'header': {
                    'namespace': 'Alexa',
                    'name': 'ErrorResponse',
                    'messageId': msg_id,
                    'payloadVersion': '3'
                },
                'payload': {
                    'type': 'INTERNAL_ERROR',
                    'message': str(e)
                }
            }
        }
```

### 2.3 Package & Deploy Lambda

```bash
zip lambda.zip lambda_function.py

aws lambda create-function \
  --function-name HomeAssistant-AlexaSmartHome \
  --runtime python3.12 \
  --role arn:aws:iam::<YOUR_ACCOUNT_ID>:role/HomeAssistant-Alexa-Role \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://lambda.zip \
  --timeout 10 \
  --environment "Variables={BASE_URL=https://your-ha-domain:port,DEBUG=true}" \
  --region us-east-1
```

### 2.4 Grant Alexa Permission to Invoke Lambda

```bash
aws lambda add-permission \
  --function-name HomeAssistant-AlexaSmartHome \
  --statement-id "alexa-smart-home-trigger" \
  --action "lambda:InvokeFunction" \
  --principal "alexa-connectedhome.amazon.com" \
  --region us-east-1
```

Note the output **Function ARN** (e.g. `arn:aws:lambda:us-east-1:<ID>:function:HomeAssistant-AlexaSmartHome`).

---

## Step 3: Create AWS API Gateway (Port 443 Proxy)

### Why is this necessary?
Amazon's OAuth server strictly enforces that the **Access Token URI** runs on standard **port 443**. If your ISP blocks port 443 or your router forwards a custom port (like `:18123` or `:8443`), Amazon's backend server will reject or fail the token exchange with `Unable to link the skill at this time`.

An AWS API Gateway HTTP API resolves this by listening on port 443 with native Amazon SSL and proxying requests transparently to your custom Home Assistant port.

```bash
aws apigatewayv2 create-api \
  --name "HA-Alexa-Proxy" \
  --protocol-type HTTP \
  --target "https://your-ha-domain:port" \
  --region us-east-1
```

Note the **ApiEndpoint** from the output:
`https://<api-id>.execute-api.us-east-1.amazonaws.com`

---

## Step 4: Configure Alexa Developer Console

1. Navigate to [developer.amazon.com/alexa/console/ask](https://developer.amazon.com/alexa/console/ask).
2. Click **Create Skill**:
   - **Skill Name**: `Home Assistant`
   - **Primary Locale**: `Portuguese (BR)` (or your preferred language)
   - **Model**: `Smart Home`
   - **Hosting**: `Provision your own`
3. In **Smart Home** settings:
   - **Payload Version**: `v3`
   - **Default endpoint**: Paste your Lambda ARN:
     `arn:aws:lambda:us-east-1:<ID>:function:HomeAssistant-AlexaSmartHome`
   - Click **Save**.
4. In the left navigation menu, click **ACCOUNT LINKING**:
   - **Authorization URI**: Point directly to Home Assistant:
     ```text
     https://your-ha-domain:port/auth/authorize
     ```
   - **Access Token URI**: Point to the AWS API Gateway (Port 443):
     ```text
     https://<api-id>.execute-api.us-east-1.amazonaws.com/auth/token
     ```
   - **Client ID**:
     ```text
     https://pitangui.amazon.com/
     ```
     *(Include the trailing slash)*
   - **Client Secret**: `homeassistant_alexa` *(Arbitrary value; required by Amazon)*
   - **Client Authentication Scheme**: **`Credentials in request body`** *(Do NOT use HTTP Basic)*
   - **Scope**: Add `smart_home`
5. Click **Save** in the top right corner.

---

## Step 5: Link the Skill in the Alexa App

1. Open the **Amazon Alexa App** on your smartphone.
2. Go to **More > Skills & Games > Your Skills > Dev tab**.
3. Tap **Home Assistant** and select **Enable to Use**.
4. Log in using your Home Assistant username and password.
5. Grant access and wait for discovery to complete.

---

## Common Gotchas & Troubleshooting

### 1. Error: "Unable to link the skill at this time. Please try again later."
* **Symptom**: You enter your Home Assistant credentials, but immediately see a yellow warning triangle with this error.
* **Root Cause**: Amazon's backend server attempted to contact your `Access Token URI` on a non-standard port (e.g., `:18123` or `:8123`). Amazon rejects non-443 ports or times out if port 443 is blocked by your residential ISP.
* **Fix**: Ensure `Access Token URI` uses the AWS API Gateway endpoint (`https://<id>.execute-api.us-east-1.amazonaws.com/auth/token`) running on port 443.

### 2. Error: "error: invalid redirect uri"
* **Symptom**: Tapping "Enable to Use" opens Home Assistant but immediately displays `error: invalid redirect uri` before showing the login form.
* **Root Cause**: Amazon uses regional OAuth redirect endpoints. Americas/Brazil accounts use `https://pitangui.amazon.com/`, while European accounts use `https://layla.amazon.com/`. Home Assistant's OAuth security checks that `redirect_uri.startswith(client_id)`.
* **Fix**: Change **Client ID** in the Alexa Developer Console to `https://pitangui.amazon.com/` (with trailing slash) for Americas/Brazil, or `https://layla.amazon.com/` for Europe.

### 3. Stuck Login Form (Form Disappears and Hangs)
* **Symptom**: If `Authorization URI` is routed through the API Gateway, submitting username and password makes the form disappear while the page remains blank/stuck.
* **Root Cause**: Home Assistant's interactive frontend requires direct browser communication for session cookies, WebSocket handshakes, and login flow IDs without proxy interference.
* **Fix**: Keep **Authorization URI** pointing directly to your Home Assistant URL (`https://your-ha-domain:port/auth/authorize`). Only the **Access Token URI** should route through the API Gateway.

### 4. Token Exchange Rejection (HTTP 400 Bad Request)
* **Symptom**: Linking fails during token exchange.
* **Root Cause**: Setting **Client Authentication Scheme** to `HTTP Basic (Recommended)`. Home Assistant expects client credentials inside the request body.
* **Fix**: Always select **`Credentials in request body`** in the Account Linking configuration.

### 5. Alexa Discovers All Entities (Ignoring "Expose" Settings)
* **Symptom**: Over 200+ entities (including test sensors, automations, and cameras) are discovered by Alexa even after clearing the UI Expose list.
* **Root Cause**: Home Assistant Core's native `Settings > Voice Assistants > Expose` screen is tied to Home Assistant Cloud (Nabu Casa). When using a manual `alexa: smart_home:` configuration, Home Assistant defaults to exposing 100% of compatible entities unless a static filter is written in YAML.
* **Fix**: Install this integration ([ha-alexa-assistant](https://github.com/alissonpdc/ha-alexa-assistant)) to bridge manual Alexa discovery directly to the native UI Expose manager!
