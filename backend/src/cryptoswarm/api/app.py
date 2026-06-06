from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from cryptoswarm.api.routes import health, positions, trades, circuit, signal, sse, dashboard
from cryptoswarm.api.routes import login


def create_app() -> FastAPI:
    app = FastAPI(title="CryptoSwarm", version="0.1.0")

    @app.exception_handler(StarletteHTTPException)
    async def auth_redirect(request: Request, exc: StarletteHTTPException):
        if exc.status_code == 401 and not request.url.path.startswith("/login"):
            return RedirectResponse(url="/login")
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

    app.include_router(login.router)
    app.include_router(health.router)
    app.include_router(positions.router)
    app.include_router(trades.router)
    app.include_router(circuit.router)
    app.include_router(signal.router)
    app.include_router(sse.router)
    app.include_router(dashboard.router)
    return app
