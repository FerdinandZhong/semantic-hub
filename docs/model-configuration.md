# Model configuration

Open [Model configuration](http://127.0.0.1:8084/demo/llm).
Draft generation, Playground, and embeddings have independent profiles.

## Enter a key directly

1. Choose **Custom OpenAI-compatible endpoint**.
2. Enter the model identifier and base URL.
3. Set **Authentication** to **Enter API key**.
4. Paste the key into the masked **API key** field.
5. Select **Save settings**.
6. Select **Test saved connection**.

For OpenAI, use `https://api.openai.com/v1` as the base URL.
Saving credentials does not establish that the selected model supports the required request format.
Use the saved connection test to check the configured provider.

GPT-5.4 Chat Completions uses `max_completion_tokens`.
The client sets reasoning effort to `none` for this lightweight path and omits sampling controls.
The former `max_tokens` request produced HTTP 400; a corrected live request returned `OK` using the configured OpenAI token file.
References: [GPT-5.4](https://developers.openai.com/api/docs/models/gpt-5.4), [Chat Completions request fields](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create).

The input clears after saving. The page shows whether a key is saved.
Leave the field blank to keep that key when changing other settings.
Enter a replacement key to rotate it.
Select **Remove saved API key**, then save, to remove the active stored credential.
These actions apply only to the selected profile.

## Other authentication options

Choose **Use environment variable** for an existing server environment reference, such as `INFERENCE_TOKEN`.
This field accepts the variable name, not its secret value.
**Inherit launch settings** continues to use the launch configuration and its credential.
Choosing direct-key authentication never silently falls back to an environment credential.

## Local credential storage

The server encrypts directly entered keys with Fernet before storing them in `llm-settings.sqlite`.
The local encryption key is `<state-root>/.model-secrets/key`.
The directory uses mode `0700`; the encryption key file uses mode `0600`.
API responses return a saved-key indicator, never the secret or encrypted credential.
Configuration validation errors omit submitted values.
Settings and key updates share a transaction with revision checking.

This is local encryption, not an enterprise secret manager.
A process that can read both the database and encryption key can decrypt credentials.
Back up the encryption key securely with the workspace; keep it out of source control and shared exports.
Use HTTPS for configuration pages hosted remotely.

## Verification

The browser check uses isolated state and a local fake provider.
It checks masked input, save, reload, blank-field retention, removal, and authenticated connection testing.
It does not modify the user's profiles or validate a particular external provider model.
See [browser verification](model-credentials-verification.json).
