"""Rotating proxy utilities for anti-ban protection."""

import random
import time
import requests

# Placeholder proxy pool. In production: use paid rotating proxy service
# (BrightData, Smartproxy, IPRoyal) and refresh via API.
PROXY_POOL = [
    "http://103.23.224.36:8080",
    "http://47.95.47.5:8080",
    "http://139.99.122.244:3128",
    "http://43.248.157.229:8080",
    "http://51.159.69.189:8080",
]


def get_random_proxy():
    return random.choice(PROXY_POOL) if PROXY_POOL else None


def is_proxy_working(proxy_url, test_url="https://httpbin.org/ip", timeout=5):
    try:
        proxies = {"http": proxy_url, "https": proxy_url}
        response = requests.get(test_url, proxies=proxies, timeout=timeout)
        return response.status_code == 200
    except Exception:
        return False


def get_working_proxy(max_attempts=10):
    for _ in range(max_attempts):
        proxy = get_random_proxy()
        if proxy and is_proxy_working(proxy):
            return proxy
        time.sleep(1)
    return None
