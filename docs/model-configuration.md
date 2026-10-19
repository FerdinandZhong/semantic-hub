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

## Older and newer OpenAI models

Request routing follows the configured model ID. Existing profiles and default models remain unchanged.

| Configured model | Text and tool protocol | Request behavior |
| --- | --- | --- |
| GPT-4o and unrecognized compatible model IDs | Chat Completions | Existing token and temperature fields |
| GPT-5 / GPT-5.1+ including GPT-5.4 | Chat Completions | Completion-token budget; existing GPT-5.1+ `none` reasoning behavior retained |
| GPT-6 family, including `gpt-6.1-sol` | Responses | Low reasoning; output-token budget; no sampling controls |

GPT-6 text calls use a minimum 1,024-token budget because reasoning consumes the same budget as visible output.
The Playground agent uses a bounded 2,000-token output budget per runtime request.
A provider response marked incomplete fails explicitly rather than becoming a partial answer.
Custom endpoints must implement the protocol selected for the model ID.
Unknown model aliases retain legacy behavior; their vendor-specific compatibility is not inferred automatically.

To use GPT-6.1 Sol:

1. Open **Model configuration → Model playground**.
2. Choose **Custom OpenAI-compatible endpoint**.
3. Set **Model** to `gpt-6.1-sol`.
4. Set **Base URL** to `https://api.openai.com/v1`.
5. Enter or retain an OpenAI API key with access to that model.
6. Save settings and select **Test saved connection**.
7. Open Playground and select a published semantic version.
8. Interpret a question and inspect its scope before execution.

CAI `CDSW_APIV2_KEY` authenticates the Hub's ingress. It is separate from the OpenAI model-provider key.
The implementation does not replace a saved model automatically.

The official [GPT-6.1 Sol documentation](https://developers.openai.com/api/docs/models/gpt-6.1-sol)
requires Responses for tool calling and supports `low` reasoning.
The runtime adapter declares that capability explicitly for custom provider routes.
Text, tool calls, reasoning items, tool results, and usage accounting follow the selected protocol.
Document visual extraction keeps its existing Chat Completions JSON-schema contract with model-compatible generation fields.

Live validation covers GPT-4o, GPT-5.4, and GPT-6.1 Sol.
All three passed connection testing, 74.1% supported-cohort execution, missing-period rejection, and unsupported-geography rejection.
See [model compatibility results](model-compatibility-verification.json).
These checks establish the tested paths, not general natural-language correctness or every vendor model's compatibility.

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

## Vision, OCR, and embedding decisions

See [the discussion record](vision-ocr-and-embeddings-discussion.md) for model roles and implemented boundaries.
Visual understanding uses the draft model; optional retrieval uses a separate text-embedding profile.
A separate OCR service is not required for the existing visual workflow.
