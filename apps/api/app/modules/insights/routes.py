import asyncio
import logging
import threading
import time
from collections import defaultdict, deque

import requests
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, StreamingResponse

from app.core import config

from . import data

log = logging.getLogger(__name__)
router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("")
def insights(sample: bool = Query(True, description="Add a generated, clearly labelled sample history")):
    """Tables for the AG Studio dashboard. Read-only."""
    return data.build(sample)


# ------------------------------------------------------------------ Studio AI proxy
# AG Studio's assistant runs in the browser and speaks the OpenAI Responses API. It posts here; we add
# the Groq key (it never reaches the browser), pin the model, drop what Groq doesn't support, cap the
# output and stream Groq's reply straight back.
GROQ_RESPONSES_URL = "https://api.groq.com/openai/v1/responses"
UNSUPPORTED = ("store", "include", "previous_response_id", "truncation", "safety_identifier",
               "prompt_cache_key", "prompt", "metadata", "user", "service_tier", "background")
MAX_OUTPUT_TOKENS = 4000
RETRIES = 5          # Groq's free plan allows 8K tokens/minute per model: wait out short 429s instead of failing
MAX_WAIT_SECONDS = 20
MAX_BODY_BYTES = 400_000
RATE = (40, 60)  # requests per window (seconds) per visitor: a public demo spends your Groq quota
_hits: dict[str, deque] = defaultdict(deque)
_hits_lock = threading.Lock()


def _allow(key: str) -> bool:
    now = time.monotonic()
    with _hits_lock:
        q = _hits[key]
        while q and now - q[0] > RATE[1]:
            q.popleft()
        if len(q) >= RATE[0]:
            return False
        q.append(now)
        return True


def clean_body(body: dict) -> dict:
    out = {k: v for k, v in body.items() if k not in UNSUPPORTED}
    # The browser picks one of the allowed models per agent; anything else gets the default.
    out["model"] = out.get("model") if out.get("model") in config.STUDIO_AI_MODELS else config.STUDIO_AI_MODEL
    out["max_output_tokens"] = min(int(out.get("max_output_tokens") or MAX_OUTPUT_TOKENS), MAX_OUTPUT_TOKENS)
    # Groq is stateless: replayed reasoning items can't be matched to a stored response, so drop them.
    if isinstance(out.get("input"), list):
        out["input"] = [i for i in out["input"] if not (isinstance(i, dict) and i.get("type") == "reasoning")]
    if not str(out["model"]).startswith("openai/gpt-oss"):
        out.pop("reasoning", None)
    else:
        out["reasoning"] = {"effort": "low"}  # dashboard work is tool calls, not deep thought: faster and fewer tokens
    for t in out.get("tools") or []:
        if isinstance(t, dict):
            t.pop("strict", None)
    out.pop("parallel_tool_calls", None)
    return out


@router.get("/ai/status")
def ai_status():
    return {"enabled": bool(config.GROQ_API_KEY), "model": config.STUDIO_AI_MODEL, "models": config.STUDIO_AI_MODELS}


@router.post("/ai/responses")
async def ai_responses(request: Request):
    if not config.GROQ_API_KEY:
        return JSONResponse({"error": {"message": "The assistant needs GROQ_API_KEY on the API server."}}, 503)
    raw = await request.body()
    if len(raw) > MAX_BODY_BYTES:
        return JSONResponse({"error": {"message": "This conversation is too long. Start a new one."}}, 413)
    visitor = request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[0].strip()
    if not _allow(visitor):
        return JSONResponse({"error": {"message": "Too many requests. Wait a minute and try again."}}, 429)
    try:
        body = clean_body(await request.json())
    except (ValueError, TypeError) as e:
        raise HTTPException(400, "Request body must be JSON.") from e

    def post():
        return requests.post(
            GROQ_RESPONSES_URL, json=body, stream=True, timeout=(10, 120),
            headers={"Authorization": f"Bearer {config.GROQ_API_KEY}", "Content-Type": "application/json"},
        )

    for attempt in range(RETRIES + 1):
        try:
            upstream = await run_in_threadpool(post)  # keep the event loop free while Groq answers
        except requests.RequestException as e:
            log.warning("Groq responses call failed: %s", type(e).__name__)
            return JSONResponse({"error": {"message": "Couldn't reach the AI. Try again."}}, 502)
        if upstream.status_code != 429 or attempt == RETRIES:
            break
        try:
            wait = float(upstream.headers.get("retry-after", "3"))
        except ValueError:
            wait = 3.0
        upstream.close()
        if wait > MAX_WAIT_SECONDS:
            break
        log.info("Groq rate limit on %s, retrying in %.1fs", body["model"], wait)
        await asyncio.sleep(wait + 0.3)

    if not upstream.ok:
        try:
            err = upstream.json()
        except ValueError:
            err = {"error": {"message": f"AI error (HTTP {upstream.status_code})"}}
        upstream.close()
        log.warning("Groq responses %s: %s", upstream.status_code, str(err)[:300])
        if upstream.status_code == 429:
            err = {"error": {"message": "The free AI plan is busy (tokens per minute). Wait a minute and ask again."}}
        return JSONResponse(err, upstream.status_code)

    def relay():
        try:
            for chunk in upstream.iter_content(chunk_size=None):
                if chunk:
                    yield chunk
        finally:
            upstream.close()

    return StreamingResponse(relay(), media_type=upstream.headers.get("Content-Type", "text/event-stream"),
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})
