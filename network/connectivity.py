"""
Lightweight connectivity check.

Opens a raw socket instead of fetching a webpage -- this stays fast
(a couple hundred ms when online, times out quickly when offline) so
it's cheap to call on every single sensor loop.
"""

import socket

from config.settings import RUN_MODE, CONNECTIVITY_CHECK_TIMEOUT


def is_online() -> bool:
    if RUN_MODE == "offline":
        return False
    if RUN_MODE == "online":
        return True

    try:
        socket.setdefaulttimeout(CONNECTIVITY_CHECK_TIMEOUT)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
        return True
    except OSError:
        return False
