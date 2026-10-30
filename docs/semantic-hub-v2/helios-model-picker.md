# Link an existing Helios model

Hub now offers organization and model selection instead of manual ID entry.
The picker links an existing model. It does not create native models or import semantic releases.

```text
Builders & connections → Link a workspace → Select organization → Select model
                                                              |
                                      Save → Recheck access → Store model reference
```

1. Open **Builders & connections** and select **Link a workspace** under your Helios provider.
2. Enter a display name for the Hub workspace.
3. For hosted Helios, enter your CAI API key and select **Load organizations**.
4. Select an organization, then select a model that Helios permits you to read.
5. Select **Save**, then open the linked workspace from the workspace cards.

The local review instance works without a key because its loopback Helios server uses the configured development identity.
Select **Local review → Empty review model** for this local fixture.
The fixture contains no published model or configured query backend.

## Authorization and storage

Hub sends only the explicitly supplied key to the registered provider API origin.
It does not forward the Hub bearer token, browser cookies, or user identity headers.
It does not substitute an application-owner credential from the server environment.
The password field clears when the dialog closes, including Escape and successful save.
The implementation does not persist the key in browser storage or Hub state.

Discovery calls native `/api/v1/organizations` and `/api/v1/models?organization_id=...`.
The latter returns a model list filtered by the native authorization policy.
Saving calls `/api/v1/models/{id}` again and checks that its organization matches the selected organization.
Revoked access therefore prevents a new link even after successful discovery.
Repeated saves of the same provider, organization, and model reuse the existing reference and display name.

The Hub catalog remains shared among authorized Hub application users.
A catalog link does not grant access to the native model. Helios checks access when the user opens it.
Hosted identity propagation through CAI ingress still requires live acceptance testing.
If the supplied key cannot establish a native principal, discovery fails without an identity-header workaround.

Requests use bounded timeouts and response sizes. Hub does not follow provider redirects.
Login redirects, denied access, malformed responses, and provider outages produce explicit errors.
Discovery and save responses use `Cache-Control: no-store`.

## Verification

Backend tests cover separate caller keys, header isolation, redirects, malformed responses, empty lists, revoked access, and idempotent saves.
The browser tests exercise the actual local Helios review model and injected UI failure responses.
The integrated AMP/provider run passed 84 tests; the final legacy-reference compatibility check brought provider tests to 36 passing.
Picker and full workspace browser checks passed with no JavaScript errors at desktop and mobile widths.

```bash
.venv-semantic-hub/bin/python -m pytest tests/providers tests/amp -q
python tests/providers/browser/model_picker.py --base-url http://127.0.0.1:8197
```

Run browser write tests against disposable Hub state. The native review model is read only during these tests.
The existing full workspace browser smoke now selects the native local review model through the picker.
