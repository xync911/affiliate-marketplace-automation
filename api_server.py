"""FastAPI application entrypoint for affiliate marketplace automation.

Run: python -m uvicorn api_server:app --host 0.0.0.0 --port 8000
"""

import os
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

import docker
from docker.errors import DockerException, NotFound, APIError
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
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

# Enable CORS for dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Docker client
try:
    docker_client = docker.from_env()
    logger.info("Docker client initialized")
except DockerException as e:
    docker_client = None
    logger.warning(f"Docker client unavailable: {e}")


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


@app.get("/api/docker/status")
async def docker_status():
    """Get Docker container status for all services."""
    if not docker_client:
        raise HTTPException(status_code=503, detail="Docker client unavailable")
    
    try:
        containers = docker_client.containers.list(all=True)
        
        status_data = {
            "total_containers": len(containers),
            "healthy_services": 0,
            "containers": []
        }
        
        for container in containers:
            attrs = container.attrs
            state = attrs["State"]
            health = state.get("Health", {}).get("Status", "none")
            
            if health == "healthy" or (state["Status"] == "running" and health == "none"):
                status_data["healthy_services"] += 1
            
            status_data["containers"].append({
                "id": container.short_id,
                "name": container.name,
                "status": state["Status"],
                "health": health,
                "image": attrs["Config"]["Image"],
                "created": attrs["Created"],
                "started_at": state.get("StartedAt"),
            })
        
        return JSONResponse(status_data)
    except APIError as e:
        raise HTTPException(status_code=500, detail=f"Docker API error: {str(e)}")


@app.get("/api/docker/logs/{container_name}")
async def docker_logs(container_name: str, tail: int = 100):
    """Get logs from specific container."""
    if not docker_client:
        raise HTTPException(status_code=503, detail="Docker client unavailable")
    
    try:
        container = docker_client.containers.get(container_name)
        logs = container.logs(tail=tail, timestamps=True).decode("utf-8")
        return JSONResponse({"container": container_name, "logs": logs.split("\n")})
    except NotFound:
        raise HTTPException(status_code=404, detail=f"Container '{container_name}' not found")
    except APIError as e:
        raise HTTPException(status_code=500, detail=f"Docker API error: {str(e)}")


@app.get("/api/docker/metrics")
async def docker_metrics():
    """Get system metrics from running containers."""
    if not docker_client:
        raise HTTPException(status_code=503, detail="Docker client unavailable")
    
    try:
        containers = docker_client.containers.list()
        
        metrics = {
            "timestamp": datetime.utcnow().isoformat(),
            "containers": []
        }
        
        for container in containers:
            try:
                stats = container.stats(stream=False)
                cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - stats["precpu_stats"]["cpu_usage"]["total_usage"]
                system_delta = stats["cpu_stats"]["system_cpu_usage"] - stats["precpu_stats"]["system_cpu_usage"]
                cpu_percent = (cpu_delta / system_delta) * 100.0 if system_delta > 0 else 0.0
                
                mem_usage = stats["memory_stats"].get("usage", 0)
                mem_limit = stats["memory_stats"].get("limit", 1)
                mem_percent = (mem_usage / mem_limit) * 100.0
                
                metrics["containers"].append({
                    "name": container.name,
                    "cpu_percent": round(cpu_percent, 2),
                    "memory_percent": round(mem_percent, 2),
                    "memory_usage_mb": round(mem_usage / (1024 * 1024), 2),
                })
            except Exception as e:
                logger.warning(f"Failed to get stats for {container.name}: {e}")
        
        return JSONResponse(metrics)
    except APIError as e:
        raise HTTPException(status_code=500, detail=f"Docker API error: {str(e)}")


@app.post("/api/docker/{action}/{container_name}")
async def docker_control(action: str, container_name: str):
    """Control container: start, stop, restart."""
    if not docker_client:
        raise HTTPException(status_code=503, detail="Docker client unavailable")
    
    if action not in ["start", "stop", "restart"]:
        raise HTTPException(status_code=400, detail=f"Invalid action: {action}")
    
    try:
        container = docker_client.containers.get(container_name)
        
        if action == "start":
            container.start()
        elif action == "stop":
            container.stop()
        elif action == "restart":
            container.restart()
        
        return JSONResponse({"status": "success", "action": action, "container": container_name})
    except NotFound:
        raise HTTPException(status_code=404, detail=f"Container '{container_name}' not found")
    except APIError as e:
        raise HTTPException(status_code=500, detail=f"Docker API error: {str(e)}")


@app.get("/")
async def root():
    return JSONResponse({
        "service": "affiliate-marketplace-automation",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "dashboard": "/dashboard",
            "docs": "/docs",
            "openapi": "/openapi.json",
        },
    })


@app.get("/dashboard")
async def dashboard():
    """Serve dashboard HTML."""
    dashboard_path = Path(__file__).parent / "dashboard.html"
    if dashboard_path.exists():
        return FileResponse(dashboard_path, media_type="text/html")
    raise HTTPException(status_code=404, detail="Dashboard not found")
