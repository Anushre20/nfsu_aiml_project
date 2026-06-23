import os
from datetime import datetime

_LOG_FILE = None


def _ensure_log():
    global _LOG_FILE
    if _LOG_FILE is None:
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
        os.makedirs(log_dir, exist_ok=True)
        _LOG_FILE = os.path.join(log_dir, "agent_debug.log")
    return _LOG_FILE


def debug(msg):
    logfile = _ensure_log()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    try:
        with open(logfile, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {msg}\n")
    except Exception:
        pass  # silently fail if we can't write
