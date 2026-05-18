import os
import json
import time
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "htbcli"
CONFIG_FILE = CONFIG_DIR / "config.json"
CACHE_FILE = CONFIG_DIR / "machines_cache.json"
ENV_VAR = "HTB_TOKEN"

CACHE_TTL = 6 * 3600  # 6 hours


def load_token() -> str | None:
    if t := os.environ.get(ENV_VAR):
        return t
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text()).get("token")
        except (json.JSONDecodeError, OSError):
            return None
    return None


def save_token(token: str) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps({"token": token}))
    CONFIG_FILE.chmod(0o600)


def clear_token() -> None:
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()


def load_machines_cache() -> list[dict] | None:
    if not CACHE_FILE.exists():
        return None
    try:
        data = json.loads(CACHE_FILE.read_text())
        if time.time() - data.get("ts", 0) < CACHE_TTL:
            return data["machines"]
    except (json.JSONDecodeError, OSError, KeyError):
        pass
    return None


def save_machines_cache(machines: list[dict]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps({"ts": time.time(), "machines": machines}))


def clear_machines_cache() -> None:
    if CACHE_FILE.exists():
        CACHE_FILE.unlink()
