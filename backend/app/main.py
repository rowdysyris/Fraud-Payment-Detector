from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.downloads import router as downloads_router
from app.api.routes import router as api_router
from app.config import settings
from app.schemas import HealthResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.ensure_directories()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Agentic Fraud Payment Investigator API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An internal server error occurred while processing the request safely.",
            "error_type": exc.__class__.__name__,
        },
    )


@app.get("/health", response_model=HealthResponse, tags=["health"])
def health_check() -> HealthResponse:
    settings.ensure_directories()
    return HealthResponse(status="ok", service=settings.app_name, version=settings.app_version)


app.include_router(api_router)
app.include_router(downloads_router)
