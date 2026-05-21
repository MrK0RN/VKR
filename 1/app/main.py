from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.routes import router
from app.config import BASE_DIR, SESSION_COOKIE_NAME
from app.logging.setup import get_logger, setup_logging

setup_logging()
logger = get_logger()

app = FastAPI(title="Дифференциальная диагностика лимфомы Ходжкина")
static_dir = BASE_DIR / "app" / "web" / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
app.include_router(router)


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        import time

        start = time.perf_counter()
        session_id = request.cookies.get(SESSION_COOKIE_NAME)
        try:
            response = await call_next(request)
        except Exception as exc:
            logger.error("engine_error", session_id=session_id, error=str(exc))
            raise
        duration_ms = (time.perf_counter() - start) * 1000
        logger.debug(
            "request",
            path=request.url.path,
            method=request.method,
            session_id=session_id,
            duration_ms=round(duration_ms, 2),
            status=response.status_code,
        )
        return response


app.add_middleware(RequestLoggingMiddleware)
