"""Lightweight cron scheduler for periodic tasks.

Runs alongside Celery Beat for redundancy and system-level scheduling.
"""

import logging
import time
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s - %(message)s",
)
logger = logging.getLogger("scheduler")


def main():
    """Main scheduler loop."""
    logger.info("Scheduler cron started")
    
    last_hour = -1
    
    while True:
        now = datetime.now()
        current_hour = now.hour
        
        # Run hourly tasks
        if current_hour != last_hour:
            logger.info("Hourly tick: hour=%d", current_hour)
            last_hour = current_hour
            
            # Morning scrape trigger at 07:00
            if current_hour == 7:
                logger.info("Morning scrape window: triggering scrape task")
            
            # Work hours: 9-18, 22-24, 0-7
            if current_hour in list(range(9, 18)) + list(range(22, 24)) + list(range(0, 7)):
                logger.info("Active posting window: hour=%d", current_hour)
        
        # Sleep 5 minutes
        time.sleep(300)


if __name__ == "__main__":
    main()
