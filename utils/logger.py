from loguru import logger
import sys
from pathlib import Path
from datetime import datetime

# Create logs directory
logs_dir = Path("logs")
logs_dir.mkdir(exist_ok=True)

# Rotate logs daily, keep 30 days
logger.remove()  # Remove default logger

# File handler with rotation
logger.add(
    logs_dir / "app_{time:YYYY-MM-DD}.log",
    rotation="00:00",  # Rotate at midnight
    retention="30 days",
    compression="zip",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <5} | {name}:{function}:{line} - {message}"
)

# Error handler
logger.add(
    logs_dir / "error_{time:YYYY-MM-DD}.log",
    rotation="00:00",
    retention="30 days",
    compression="zip",
    level="ERROR",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <5} | {name}:{function}:{line} - {message}"
)

# Console handler
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level="INFO"
)

def get_logger(name: str):
    return logger.bind(name=name)

# Enable logging in all modules
logger.info("Logging initialized with loguru")
