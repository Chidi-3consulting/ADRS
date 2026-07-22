import uvicorn
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, JSONResponse
import os
import asyncio
from datetime import datetime
from contextlib import asynccontextmanager

from app.database import engine, Base, SessionLocal
from fastapi.templating import Jinja2Templates
from app.auth import get_session

_original_template_response = Jinja2Templates.TemplateResponse

def _patched_template_response(self, request, name, context=None, *args, **kwargs):
    if context is None:
        context = {}
    context["request"] = request
    session = get_session(request)
    if session:
        context["is_platform_admin"] = session.get("is_platform_admin", False)
    else:
        context["is_platform_admin"] = False
    return _original_template_response(self, request, name, context, *args, **kwargs)

Jinja2Templates.TemplateResponse = _patched_template_response

from app.routes import (
    public, dashboard, categories, records, api_v1, app_pages, platform,
    integrations_routes, recalculations, import_records
)
from app.engine import run_retention_checks
from app.models import Organization

# Ensure DB tables exist
Base.metadata.create_all(bind=engine)

# Seed default organization if table is empty
db = SessionLocal()
try:
    if not db.query(Organization).first():
        org = Organization(
            id=1,
            name="Default Organisation",
            slug="default",
            primary_domain="default.local",
            country="NG",
            tier="core",
            status="active"
        )
        db.add(org)
        db.commit()
finally:
    db.close()

# Background scheduler task for retention engine
async def retention_scheduler_task():
    while True:
        await asyncio.sleep(600)
        db = SessionLocal()
        try:
            orgs = db.query(Organization).all()
            for org in orgs:
                run_retention_checks(db, org.id)
        except Exception as e:
            print(f"[{datetime.now()}] Scheduler error: {e}")
        finally:
            db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(retention_scheduler_task())
    yield
    task.cancel()

app = FastAPI(
    title="Automated Data Retention Solution (ADRS)",
    version="3.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    debug=True,
    lifespan=lifespan
)

# Mount Static Files
static_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "static")
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")

# Register Routers
app.include_router(public.router)
app.include_router(dashboard.router)
app.include_router(categories.router)
app.include_router(records.router)
app.include_router(app_pages.router)
app.include_router(platform.router)
app.include_router(integrations_routes.router)
app.include_router(recalculations.router)
app.include_router(import_records.router)
app.include_router(api_v1.router, prefix="/api/v1")

@app.get("/healthz")
def system_healthz():
    return JSONResponse(content={"status": "ok", "service": "ADRS Python Engine"})

@app.exception_handler(303)
async def redirect_exception_handler(request: Request, exc):
    return RedirectResponse(url="/login", status_code=303)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8200, reload=True)
