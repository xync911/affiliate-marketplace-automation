"""FastAPI application entrypoint for affiliate marketplace automation.

Run: python -m uvicorn api_server:app --host 0.0.0.0 --port 8000
"""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from loguru import logger

from utils.logger import logger  # noqa: F811  ensures logging hooks load once

# Ensure logs + data dirs exist at runtime
Path("logs").mkdir(exist_ok=True)
Path("data/schedules").mkdir(exist_ok=True)
Path("data/spin-templates").mkdir(exist_ok=True)
Path("data/output").mkdir(exist_ok=True)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

app = FastAPI(
    title="Affiliate Marketplace Automation API",
    description="Task queue orchestration, product scraping, and distribution",
    version="1.0.0",
)


@app.on_event("startup")
async def startup_event():
    logger.info("API server starting up")
    logger.info("REDIS_URL={redis_url}", redis_url=REDIS_URL)
    logger.info("OLLAMA_HOST={ollama_url}", ollama_url=OLLAMA_HOST)


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("API server shutting down")


@app.get("/health")
async def health_check():
    """Liveness probe used by Docker healthcheck."""
    return JSONResponse({"status": "healthy", "service": "api_server"})


@app.get("/")
async def root():
    return JSONResponse({
        "service": "affiliate-marketplace-automation",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "openapi": "/openapi.json",
        },
    })
