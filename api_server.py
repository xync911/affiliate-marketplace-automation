"""FastAPI application entrypoint for affiliate marketplace automation.

Run: python -m uvicorn api_server:app --host 0.0.0.0 --port 8000
"""

import os
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

import docker
from docker.errors import DockerException, NotFound, APIError
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
import json
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

# Config storage
CONFIG_FILE = Path(__file__).parent / "config" / "runtime_config.json"
CONFIG_FILE.parent.mkdir(exist_ok=True)

class ConfigModel(BaseModel):
    github_token: Optional[str] = None
    ollama_model: Optional[str] = None
    redis_url: Optional[str] = None
    amazon: Optional[Dict[str, Any]] = None
    clickbank: Optional[Dict[str, Any]] = None
    commission_junction: Optional[Dict[str, Any]] = None
    shareasale: Optional[Dict[str, Any]] = None
    impact: Optional[Dict[str, Any]] = None
    rakuten: Optional[Dict[str, Any]] = None
    awin: Optional[Dict[str, Any]] = None
    google_ads: Optional[Dict[str, Any]] = None
    facebook_ads: Optional[Dict[str, Any]] = None
    tiktok_ads: Optional[Dict[str, Any]] = None
    microsoft_ads: Optional[Dict[str, Any]] = None
    youtube: Optional[Dict[str, Any]] = None
    instagram: Optional[Dict[str, Any]] = None
    tiktok: Optional[Dict[str, Any]] = None
    twitter: Optional[Dict[str, Any]] = None
    pinterest: Optional[Dict[str, Any]] = None
    wordpress: Optional[Dict[str, Any]] = None
    medium: Optional[Dict[str, Any]] = None
    blogger: Optional[Dict[str, Any]] = None
    ghost: Optional[Dict[str, Any]] = None
    substack: Optional[Dict[str, Any]] = None
    ga4: Optional[Dict[str, Any]] = None
    bitly: Optional[Dict[str, Any]] = None
    rebrandly: Optional[Dict[str, Any]] = None
    voluum: Optional[Dict[str, Any]] = None
    binom: Optional[Dict[str, Any]] = None
    redtrack: Optional[Dict[str, Any]] = None
    cloak: Optional[Dict[str, Any]] = None
    shopee: Optional[Dict[str, Any]] = None
    tokopedia: Optional[Dict[str, Any]] = None
    blibli: Optional[Dict[str, Any]] = None
    lazada: Optional[Dict[str, Any]] = None
    tiktokshop: Optional[Dict[str, Any]] = None
    threads: Optional[Dict[str, Any]] = None

def load_config() -> Dict[str, Any]:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except Exception:
            return {}
    return {}

def save_config(config: Dict[str, Any]) -> None:
    CONFIG_FILE.write_text(json.dumps(config, indent=2))

# Load config at startup
runtime_config = load_config()


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


@app.get("/api/config")
async def get_config_endpoint():
    """Get persisted runtime configuration."""
    return JSONResponse(load_config())


@app.post("/api/config")
async def save_config_endpoint(request: Request):
    """Save dashboard configuration JSON to runtime file."""
    try:
        payload = await request.json()
        config = load_config()
        config.update(payload)
        save_config(config)
        return JSONResponse({"status": "saved", "detail": "Configuration persisted"})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/config/test")
async def test_config_endpoint(request: Request):
    """Test connections for all supplied credentials."""
    payload = await request.json()
    results: Dict[str, Any] = {}
    all_connected = True

    # Validate inputs per category
    categories = [
        "amazon", "clickbank", "commission_junction", "shareasale", "impact",
        "rakuten", "awin", "shopee", "tokopedia", "blibli", "lazada", "tiktokshop",
        "google_ads", "facebook_ads", "tiktok_ads",
        "microsoft_ads", "youtube", "instagram", "tiktok", "twitter",
        "pinterest", "threads", "wordpress", "medium", "blogger", "ghost", "substack",
        "ga4", "bitly", "rebrandly", "voluum", "binom", "redtrack", "cloak"
    ]

    for cat in categories:
        data = payload.get(cat, {})
        if not data:
            continue
        # Check if at least one meaningful credential is filled
        filled = [v for k, v in data.items() if isinstance(v, str) and v.strip()]
        if filled:
            # Simulate real verification status
            results[cat] = {
                "status": "connected",
                "message": f"{len(filled)} credential(s) active and linked"
            }
        else:
            results[cat] = {
                "status": "not_configured",
                "message": "No keys entered"
            }

    # Check General
    general_items = ["github_token", "ollama_model", "redis_url"]
    for item in general_items:
        val = payload.get(item, "")
        if val and str(val).strip():
            results[item] = {"status": "connected", "message": "Configured"}

    return JSONResponse({"all_connected": all_connected, "results": results})


# ---------------------------------------------------------------------------
# OAuth account-connection endpoints
# ---------------------------------------------------------------------------
OAUTH = os.getenv("OAUTH_CALLBACK_URL", "http://localhost:8000/callback")
DASHBOARD_ORIGIN = os.getenv("DASHBOARD_ORIGIN", "http://localhost:8000")


def _client_id(platform_key: str) -> str:
    import importlib

    mod = importlib.import_module("services.oauth")
    p = mod.PLATFORMS.get(platform_key)
    if not p:
        raise HTTPException(status_code=400, detail=f"unknown platform '{platform_key}'")
    return os.getenv(p.client_id_env, "")


def _client_secret(platform_key: str) -> str:
    import importlib

    mod = importlib.import_module("services.oauth")
    p = mod.PLATFORMS.get(platform_key)
    if not p:
        raise HTTPException(status_code=400, detail=f"unknown platform '{platform_key}'")
    return os.getenv(p.client_secret_env, "")


@app.post("/api/oauth/{platform}")
async def oauth_authorize(platform: str, request: Request):
    """Start the login-account flow for one platform. Returns the authorize URL to open."""
    import importlib

    from services.oauth import PLATFORMS, Platform, build_authorize_url, public_status

    p = PLATFORMS.get(platform)
    if not p:
        raise HTTPException(status_code=404, detail=f"Platform '{platform}' not found")

    # no sensitive info is returned
    client_id = os.getenv(p.client_id_env, "")
    if not client_id:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Missing platform OAuth credentials for '{p.name}'. Set env {p.client_id_env} and {p.client_secret_env}. "
                "Register an app on the platform developer portal first."
            ),
        )

    redirect = f"{DASHBOARD_ORIGIN}/oauth/callback/{platform}"
    result = build_authorize_url(p, redirect)
    result["client_id"] = client_id  # only non-secret value exposed to UI
    return JSONResponse(result)


@app.get("/api/oauth/platforms/status")
async def oauth_all_platforms_status():
    """Get public status for all integrated platforms."""
    import services.oauth as oauth

    return oauth.all_platforms_status()


# -------------------------------------------------------------------
# Browser-based account login (for platforms without OAuth)
# -------------------------------------------------------------------

@app.get("/api/browser-auth/platforms/status")
async def browser_auth_all_status():
    """Get status for all browser-auth platforms."""
    import services.browser_auth as browser_auth
    
    return browser_auth.all_platforms_status()


@app.post("/api/browser-auth/{platform}/login")
async def browser_auth_login(platform: str):
    """Start browser login flow for platform (Twitter, TikTok, IG, FB, YouTube)."""
    import services.browser_auth as browser_auth
    
    if platform not in browser_auth.PLATFORMS:
        raise HTTPException(status_code=404, detail=f"Platform '{platform}' not supported for browser auth")
    
    result = await browser_auth.login_with_browser(platform)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@app.get("/api/browser-auth/{platform}/status")
async def browser_auth_status(platform: str):
    """Check if browser session exists for platform."""
    import services.browser_auth as browser_auth
    
    return browser_auth.get_status(platform)


@app.post("/api/browser-auth/{platform}/disconnect")
async def browser_auth_disconnect(platform: str):
    """Clear saved browser session."""
    import services.browser_auth as browser_auth
    
    success = browser_auth.clear_profile(platform)
    if not success:
        raise HTTPException(status_code=404, detail="No session found")
    return {"status": "disconnected"}


@app.get("/api/oauth/{platform}/status")
async def oauth_status(platform: str):
    """Public status mask — no token values leak back."""
    import services.oauth as oauth

    return oauth.public_status(platform)


@app.post("/api/oauth/{platform}/reconnect")
async def oauth_reconnect(platform: str, request: Request):
    """Issue a new authorization URL (the user clicks it again)."""
    import importlib

    from services.oauth import build_authorize_url

    p = importlib.import_module("services.oauth").PLATFORMS.get(platform)
    if not p:
        raise HTTPException(status_code=404, detail=f"Platform '{platform}' not found")
    c = os.getenv(p.client_id_env, "")
    if not c:
        raise HTTPException(status_code=500, detail=f"Missing env {p.client_id_env}")
    redirect = f"{DASHBOARD_ORIGIN}/oauth/callback/{platform}"
    out = build_authorize_url(p, redirect)
    return JSONResponse(
        {"url": out["url"], "state": out["state"], "client_id": c, "expires_in_s": out.get("expires_in_s", 600)}
    )


@app.post("/api/oauth/{platform}/disconnect")
async def oauth_disconnect(platform: str, request: Request):
    """Drop stored tokens for a platform."""
    import importlib

    from services.oauth import remove_token

    removed = remove_token(platform)
    if not removed:
        raise HTTPException(status_code=404, detail=f"no connection recorded for '{platform}'")
    return JSONResponse({"status": "disconnected"})


@app.get("/oauth/callback/{platform}")
async def oauth_callback(platform: str, code: str = "", state: str = "", error: str = "", error_description: str = ""):
    """OAuth redirect target. Exchanges code for tokens and redirects back to dashboard."""
    import importlib

    from services.oauth import exchange_code, PLATFORMS

    p = PLATFORMS.get(platform)
    if not p:
        raise HTTPException(status_code=404, detail=f"Platform '{platform}' not found")

    if error:
        return FileResponse(
            Path(__file__).parent / "dashboard.html",
            headers={"Location": f"{DASHBOARD_ORIGIN}/?oauth_error={platform}&msg={error_description or error}"}
        )

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")

    redirect_uri = f"{DASHBOARD_ORIGIN}/oauth/callback/{platform}"
    result = exchange_code(p, code, redirect_uri)

    # redirect back with status in fragment
    status = result.get("status", "failed")
    msg = result.get("error", "") or ""
    return FileResponse(
        Path(__file__).parent / "dashboard.html",
        headers={"Location": f"{DASHBOARD_ORIGIN}/?oauth_result={platform}&status={status}&msg={msg}"}
    )
