# Open decisions

Please add answers below the relevant item. Implementation continues with the documented defaults.

1. **Durable Space storage:** Which PostgreSQL database and private S3-compatible upload bucket should the Space use? Local Docker uses a named volume. Production storage uses Supabase PostgreSQL and a private Hugging Face bucket; authenticated save/reload and restore remain acceptance checks.

   Answer: A private Hugging Face bucket `kaushikpaul/open-webui-surplus-data` was created for files. The owner chose Supabase PostgreSQL for chats/settings. The owner confirmed there was no existing Space data to preserve. The Supabase Session pooler URL is set as a Space Secret, the bucket is mounted at `/app/backend/data`, PostgreSQL application tables exist, and the Space has responded to `/health`.

2. **Preferred models:** Which Surplus chat, image-generation, and image-edit models do you want as defaults? The UI discovers live capability metadata and accepts exact manual IDs. Image editing remains disabled until an edit model is chosen.

   Answer: Text: `deepseek-v4-flash-0731`. Image: `venice-z-image-turbo`, chosen after `venice-gpt-image-2` returned HTTP 503 twice and z-image-turbo generated successfully on 2026-09-26. No edit default selected.

Resolved: only `SURPLUS_API_KEY` is supported as an environment credential reference, per your follow-up. The existing `.env` has been preserved.
