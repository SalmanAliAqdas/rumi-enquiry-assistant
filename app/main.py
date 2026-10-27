import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import Settings
from app.db import init_db, make_engine
from app.gemini import build_processor
from app.private import private_api
from app.private import router as private_router
from app.public import router as public_router
from app.services import DEMO_LABEL

ROOT = Path(__file__).parent


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.engine = make_engine(settings.database_url)
        init_db(app.state.engine)
        yield
        app.state.engine.dispose()

    app = FastAPI(title="Rumi Enquiry Assistant", version="0.2.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.processor, app.state.processing_timeout = build_processor(settings)
    app.state.processing_mode = (
        settings.processor_mode if settings.processor_mode in {"demo", "gemini"} else "unconfigured"
    )
    app.state.processing_model = (
        settings.gemini_model
        if (
            app.state.processing_mode == "gemini"
            and re.fullmatch(r"gemini-[a-z0-9.-]{1,80}", settings.gemini_model)
        )
        else None
    )
    app.state.templates = Jinja2Templates(directory=ROOT / "templates")
    app.state.templates.env.globals["demo_label"] = DEMO_LABEL
    app.state.templates.env.globals["processing_label"] = (
        DEMO_LABEL
        if settings.processor_mode == "demo"
        else "Gemini processing — manual review required."
        if settings.processor_mode == "gemini"
        else "Processing configuration needs administrator attention."
    )
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]", "testserver"]
    )

    @app.middleware("http")
    async def protect_responses(request: Request, call_next):
        if request.method in {"POST", "PATCH", "PUT"}:
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 24000:
                    return JSONResponse({"detail": "Request is too large."}, status_code=413)
            request._body = bytes(body)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        # Swagger uses its own CDN assets; application pages use only local assets.
        if request.url.path not in {"/docs", "/redoc", "/docs/oauth2-redirect"}:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; style-src 'self'; "
                "img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
            )
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        # Never reflect supplied passwords or original private enquiry data into errors.
        errors = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
        return JSONResponse({"detail": errors}, status_code=422)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        if exc.status_code == 401 and request.url.path.startswith("/admin"):
            if request.url.path != "/admin/login":
                return RedirectResponse("/admin/login", status_code=303)
        return await http_exception_handler(request, exc)

    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
    app.include_router(public_router)
    app.include_router(private_router)
    app.include_router(private_api)
    return app


app = create_app()
