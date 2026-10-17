"""The FastAPI app: middleware, error handling and routers. New features add a router here, a service for their
rules, a repository for each outside system they talk to, and models for their bodies."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.core.config import allowed_origins
from backend.core.errors import AppError
from backend.routers import github, health

app = FastAPI(title="Majidev backend", docs_url=None, redoc_url=None, openapi_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins(),
    allow_methods=["POST"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.exception_handler(AppError)
async def app_error(_: Request, err: AppError) -> JSONResponse:
    return JSONResponse({"detail": err.detail}, status_code=err.status_code)


app.include_router(health.router)
app.include_router(github.router)
