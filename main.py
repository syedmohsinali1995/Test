"""
Urdu Real Estate AI Calling Agent — SaaS Platform
Multi-tenant | JWT Auth | Web Dashboard | Bulk Calling
"""

import asyncio
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from db.database import init_db
from routers import auth, admin, setup, calls, records
from webhooks.handler import handle_vapi_event, handle_tool_call
from services.call_retry import start_retry_worker
from config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    task = asyncio.create_task(start_retry_worker())
    print("[App] Database ready. Retry worker started.")
    yield
    task.cancel()


app = FastAPI(
    title="Urdu Real Estate AI Calling Agent",
    version="4.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(setup.router)
app.include_router(calls.router)
app.include_router(records.router)

# ── Static frontend ───────────────────────────────────────────────────────────
app.mount("/app", StaticFiles(directory="frontend", html=True), name="frontend")


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return RedirectResponse("/app/login.html")


@app.get("/health")
def health():
    return {"status": "running", "version": "4.0.0"}


@app.get("/debug/env")
def debug_env():
    """Temporary: check if env vars are loaded correctly on Railway."""
    import os
    email = os.environ.get("SUPER_ADMIN_EMAIL", "NOT SET")
    pwd   = os.environ.get("SUPER_ADMIN_PASSWORD", "NOT SET")
    return {
        "SUPER_ADMIN_EMAIL":    email,
        "SUPER_ADMIN_PASSWORD": "SET" if pwd != "NOT SET" else "NOT SET",
        "SECRET_KEY":           "SET" if os.environ.get("SECRET_KEY") else "NOT SET",
        "PUBLIC_URL":           os.environ.get("PUBLIC_URL", "NOT SET"),
    }


# ── Per-tenant Vapi Webhooks ──────────────────────────────────────────────────
@app.post("/webhook/vapi/{tenant_id}")
async def vapi_webhook(tenant_id: str, request: Request):
    return await handle_vapi_event(tenant_id, request)


@app.post("/webhook/tool/{tenant_id}")
async def tool_webhook(tenant_id: str, request: Request):
    return await handle_tool_call(tenant_id, request)


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import os
    port = int(os.getenv("PORT", settings.port))
    uvicorn.run("main:app", host=settings.host, port=port, reload=False)
