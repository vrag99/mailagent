import os
import re
from typing import Any

ENV_VAR_RE = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)(?::-([^}]*))?\}")


def interpolate_env_vars(obj: Any) -> tuple[Any, list[str]]:
    """Recursively interpolate ${VAR} and ${VAR:-default} in YAML data."""
    errors: list[str] = []

    def _walk(value: Any, path: str) -> Any:
        if isinstance(value, dict):
            out: dict[str, Any] = {}
            for key, child in value.items():
                child_path = f"{path}.{key}" if path else str(key)
                out[key] = _walk(child, child_path)
            return out

        if isinstance(value, list):
            out_list: list[Any] = []
            for idx, child in enumerate(value):
                child_path = f"{path}[{idx}]"
                out_list.append(_walk(child, child_path))
            return out_list

        if isinstance(value, str):
            return _interpolate_string(value, path, errors)

        return value

    return _walk(obj, ""), errors


def _interpolate_string(value: str, path: str, errors: list[str]) -> str:
    def _replace(match: re.Match[str]) -> str:
        var_name = match.group(1)
        default = match.group(2)

        if var_name in os.environ:
            return os.environ[var_name]

        if default is not None:
            return default

        errors.append(
            f"Environment variable {var_name} is not set (referenced in {path or '<root>'})"
        )
        return match.group(0)

    return ENV_VAR_RE.sub(_replace, value)
