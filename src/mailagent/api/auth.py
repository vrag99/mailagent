from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timezone
from pathlib import Path

import yaml
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)

DEFAULT_API_KEYS_PATH = "/app/data/api-keys.yml"


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _load_keys(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}
    return data.get("keys", {})


def _save_keys(path: Path, keys: dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.dump({"keys": keys}, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )


def create_api_key(api_keys_path: str | None = None, name: str = "default") -> str:
    """Generate a new API key, store its hash, and return the raw key."""
    path = Path(api_keys_path or DEFAULT_API_KEYS_PATH)
    keys = _load_keys(path)

    raw_key = f"ma_{secrets.token_urlsafe(32)}"
    key_hash = _hash_key(raw_key)

    keys[key_hash] = {
        "name": name,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _save_keys(path, keys)
    return raw_key


def list_api_keys(api_keys_path: str | None = None) -> list[dict]:
    path = Path(api_keys_path or DEFAULT_API_KEYS_PATH)
    keys = _load_keys(path)
    return [
        {"hash_prefix": h[:12], "name": v["name"], "created_at": v.get("created_at", "")}
        for h, v in keys.items()
    ]


def revoke_api_key(hash_prefix: str, api_keys_path: str | None = None) -> bool:
    path = Path(api_keys_path or DEFAULT_API_KEYS_PATH)
    keys = _load_keys(path)
    to_remove = [h for h in keys if h.startswith(hash_prefix)]
    if not to_remove:
        return False
    for h in to_remove:
        del keys[h]
    _save_keys(path, keys)
    return True


def create_auth_dependency(api_keys_path: str | None = None) -> Depends:
    path = Path(api_keys_path or DEFAULT_API_KEYS_PATH)

    async def verify_api_key(
        credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
    ) -> str:
        if not path.exists():
            return "anonymous"

        if credentials is None:
            raise HTTPException(status_code=401, detail="Missing API key")

        key_hash = _hash_key(credentials.credentials)
        keys = _load_keys(path)

        if key_hash not in keys:
            raise HTTPException(status_code=401, detail="Invalid API key")

        return keys[key_hash].get("name", "unknown")

    return Depends(verify_api_key)
