import json
import logging
from pathlib import Path
from tempfile import gettempdir
from functools import lru_cache
from datetime import datetime

# 🔐 Runtime-safe file path (will not trigger reloads)
KEY_PATH = Path(gettempdir()) / "today_instrument_keys.json"
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.info("Keys will be saved to: %s", KEY_PATH)


def save_instrument_keys(keys: list[str]) -> None:
    try:
        with open(KEY_PATH, "w", encoding="utf-8") as f:
            json.dump(sorted(keys), f, indent=2)
    except Exception as e:
        logger.error(f"⚠️ Error saving instrument keys: {e}")


def load_instrument_keys() -> list[str]:
    try:
        if KEY_PATH.exists():
            with open(KEY_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"⚠️ Error loading instrument keys: {e}")
    return []


def instrument_keys_exist() -> bool:
    return KEY_PATH.exists()


@lru_cache(maxsize=1)
def get_cached_instrument_keys() -> list[str]:
    return load_instrument_keys()


def get_or_generate_instrument_keys(generate_fn) -> list[str]:
    if instrument_keys_exist():
        return get_cached_instrument_keys()
    keys = generate_fn()
    save_instrument_keys(keys)
    return keys
