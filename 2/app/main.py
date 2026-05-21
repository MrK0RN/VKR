from __future__ import annotations

import uuid

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import config
from app.api.routes import router
from app.logging.setup import get_logger, setup_logging

setup_logging()
logger = get_logger("main")

app = FastAPI(title=config.APP_TITLE)
app.include_router(router)
app.mount("/static", StaticFiles(directory=str(config.BASE_DIR / "app" / "web" / "static")), name="static")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception(
        "engine_error",
        path=request.url.path,
        error=str(exc),
    )
    accept = request.headers.get("accept", "")
    if "text/html" in accept or request.url.path.startswith("/step"):
        return HTMLResponse(
            content=(
                "<!DOCTYPE html><html lang='ru'><head><meta charset='utf-8'>"
                "<title>Ошибка</title></head><body>"
                "<h1>Ошибка обработки запроса</h1>"
                "<p>Повторите действие или начните опрос заново.</p>"
                "<p><a href='/step/1'>К началу опроса</a></p>"
                "</body></html>"
            ),
            status_code=500,
        )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "request_id": getattr(request.state, "request_id", None)},
    )


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response
