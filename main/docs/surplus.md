# Surplus setup and compatibility

The production API base URL is `https://api.surplusintelligence.ai/v1`. Do not append `/chat/completions` in the connection editor. The production [chat reference](https://www.surplusintelligence.ai/docs/api-reference/chat-completions) and [image reference](https://www.surplusintelligence.ai/docs/api-reference/image-generations) were retrieved during implementation.

## Credentials and chat

Set the **server** Secret `SURPLUS_API_KEY`, and Variable `PROVIDER_SECRET_NAMES=SURPLUS_API_KEY`. In Admin Settings → Connections, add the base URL above, choose **Secret name**, and enter exactly `SURPLUS_API_KEY` in the key field. Verify and save. The browser/config exports retain the name plus `key_source: secret`; the backend resolves it for each request. Only this environment name is supported. Existing connections without source metadata retain literal-key semantics.

The authenticated catalog supplies current IDs. Surplus text choices exclude explicit non-text output modalities. Vision and function calling use catalog input modalities and `supported_features`, with native per-model settings available for corrections. Catalog presence does not guarantee an available seller. Manual exact IDs are available when metadata is incomplete. Uploaded image input/vision is independent of image generation.

Chat, Responses, embeddings, connection-backed speech, model management, pipeline requests, and Anthropic/Azure authentication branches use request-local credentials. Standard bearer and Azure/Anthropic header conventions are preserved. Session/OAuth/Entra authentication cannot be combined with Secret name mode. Conflicting custom authentication headers are rejected. Provider destinations require HTTPS; local HTTP is limited to named fixture hosts under `ALLOW_HTTP_TEST_PROVIDERS=true`, which must not be enabled in production.

## Images

In Admin Settings → Images select **OpenAI**, **Surplus** compatibility, the Surplus base URL, **Secret name**, and `SURPLUS_API_KEY`. Leave API version blank. Save to refresh model discovery, select a current generation model, and enable generation. Count defaults to one. Advanced Surplus parameters are limited to `quality`, `resolution` (`1K`, `2K`, `4K`), and `response_format` (`b64_json`, `url`). Model-specific dimensions still apply.

Editing has a separate engine/base URL/source/key/model. Choose an edit-capable model from explicit `image_edit` metadata, or enter its exact ID manually. **Leave edit size blank initially:** the live `grok-imagine-edit` check rejected 512×512 but succeeded with size omitted. Surplus edits send JSON with `image` for one input and ordered `input_images` for up to eight. Masks/inpainting are rejected. Standard OpenAI editing retains multipart requests.

Input files are read through native ownership checks and converted to bounded data URIs. Both base64 and HTTPS URL results are decoded, validated as PNG/JPEG/WebP, and uploaded through native private file storage. Provider keys are never sent to download/CDN hosts. Public-IP DNS resolution is checked at connection time, redirects are bounded/revalidated, downloads are limited to 20 MiB/45 seconds, and decoded images to 40 million pixels. Generated file links survive chat reload when database and upload storage persist.

Use native explicit image controls even if a chat model does not support function tools. Native image tools use these same backend routines. Generation has a separately bounded `SURPLUS_IMAGE_TIMEOUT` (default 180 seconds, maximum 600); requests are never automatically retried. A timeout may occur after a provider has charged, so check activity before retrying.

## Error behavior and live checks

Errors distinguish rejected keys, insufficient balance, unavailable model/seller, rate limits, and timeouts without forwarding arbitrary provider bodies. Raw upstream error text and credential suffixes are not included in user-facing diagnostic events.

Live checks on 2026-09-06: authenticated discovery returned 402 models, including 55 image-output entries; `venice-z-image-turbo` returned one valid image; `grok-imagine-edit` succeeded without a size parameter. A seller serving `openai-gpt-oss-120b` returned HTTP 200 SSE without `[DONE]`; native streaming must handle EOF. These are compatibility observations, not permanent availability promises. Full results and remaining checks are in `verification.md`.

`main/scripts/smoke_surplus.py` is an explicit, billable smoke-check command using the root `.env`. It never prints the key or automatically retries. Automated regression tests use mocks and no balance.
