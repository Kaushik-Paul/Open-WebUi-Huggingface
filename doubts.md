# Open decisions

Please add answers below the relevant item. Implementation continues with the documented defaults.

1. **Durable Space storage:** Which PostgreSQL database and private S3-compatible upload bucket should the Space use? Local Docker uses a named volume. No external infrastructure has been provisioned; Space durability requires these choices and a recreation/restore test.

   Answer: A private Hugging Face bucket `kaushikpaul/open-webui-surplus-data` was created for files. The owner chose Supabase PostgreSQL for chats/settings. Pending: Supabase Session pooler `DATABASE_URL` Secret, preservation decision for existing Space data, and read-write bucket mount at `/app/backend/data`.

2. **Preferred models:** Which Surplus chat, image-generation, and image-edit models do you want as defaults? The UI discovers live capability metadata and accepts exact manual IDs. Image generation/editing start disabled until configured to avoid silently choosing a billable model.

   Answer: Text: `deepseek-v4-flash-0731`. Image: `venice-z-image-turbo`, chosen after `venice-gpt-image-2` returned HTTP 503 twice and z-image-turbo generated successfully on 2026-09-26. No edit default selected.

Resolved: only `SURPLUS_API_KEY` is supported as an environment credential reference, per your follow-up. The existing `.env` has been preserved.
