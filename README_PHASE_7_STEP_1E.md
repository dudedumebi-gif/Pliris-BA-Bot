# Phase 7 Step 1E — Rate-Limit Evidence and Public Deployment

## Architecture

The public Render service runs two server-side processes in one container:

- FastAPI binds only to `127.0.0.1:8000`.
- Streamlit binds to Render's public `$PORT`.
- Streamlit calls FastAPI through localhost.
- OpenAI and Supabase credentials exist only in the service environment.
- The browser receives the Streamlit interface, not direct API credentials.

This one-service design reduces the public attack surface and avoids requiring a
separate public API URL for the Step 1 review deployment.

## Local rate-limit evidence

Stop the normal API and restart it with a two-request window:

```bash
export GUEST_REQUESTS_PER_WINDOW=2
export GUEST_MAX_REQUESTS_PER_SESSION=10
export GUEST_REQUEST_WINDOW_SECONDS=60

uv run uvicorn api.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```bash
uv run python scripts/smoke_rate_limit.py --allowed 2
```

Expected status sequence:

```text
400
400
429
```

The first two requests are rejected by the prompt-injection guardrail. The third
is rejected by the rate limiter and must include `Retry-After`. No grounded
model call should occur.

For UI evidence, submit the same prompt three times from one Streamlit browser
session. The third attempt must display the public rate-limit message and an
approximate retry time.

Afterward:

```bash
unset GUEST_REQUESTS_PER_WINDOW
unset GUEST_MAX_REQUESTS_PER_SESSION
unset GUEST_REQUEST_WINDOW_SECONDS
```

## Render deployment

1. Push this increment to `feature-interface-monitoring`.
2. Sign in to Render and create a new Blueprint.
3. Select this GitHub repository and the root `render.yaml`.
4. Supply the five values marked `sync: false`:
   - `OPENAI_API_KEY`
   - `SUPABASE_URL`
   - `SUPABASE_PUBLISHABLE_KEY`
   - `SUPABASE_SECRET_KEY`
   - `SUPABASE_DB_URL`
5. Create the Blueprint and wait for the service health check to pass.
6. Open the generated `onrender.com` URL in a private browser window.

Do not upload the local `.env` file to GitHub or paste secrets into issue
comments, screenshots, or chat.

## Hosted acceptance test

Using a private browser window with no project login:

1. Open the public URL.
2. Confirm only the Chat interface is visible.
3. Ask one supported BA question and confirm grounded citations.
4. Ask one context-dependent follow-up and confirm continuation.
5. Clear the conversation.
6. Confirm the exact out-of-scope response.
7. Confirm prompt-injection rejection.
8. Stop or suspend the service only after evidence is captured.

## Free-service note

A free Render web service can spin down after inactivity. That is acceptable for
public review, but the first request after inactivity can have a cold-start
delay. A paid instance removes the free-service spin-down limitation.
