from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from .utils.env import interpolate_env_vars


class ConfigError(Exception):
    """Configuration loading/validation error."""


@dataclass
class ProviderConfig:
    name: str
    type: str
    model: str
    api_key: str
    base_url: str | None = None
    timeout: int = 30
    retries: int = 1
    http_referer: str | None = None
    x_title: str | None = None


@dataclass
class KeywordMatch:
    any: list[str] | None = None
    all: list[str] | None = None


@dataclass
class WorkflowMatch:
    intent: str
    keywords: KeywordMatch | None = None


@dataclass
class WorkflowAction:
    type: str
    prompt: str | None = None
    webhook: str | None = None
    url: str | None = None
    method: str = "POST"
    headers: dict[str, str] | None = None
    payload: dict[str, Any] | None = None
    also_reply: bool = False
    also_webhook: bool = False
    webhook_url: str | None = None


@dataclass
class Workflow:
    name: str
    match: WorkflowMatch
    action: WorkflowAction


@dataclass
class Blocklist:
    from_patterns: list[str] = field(default_factory=list)
    headers: list[str] = field(default_factory=list)


@dataclass
class InboxConfig:
    address: str
    credentials: dict[str, str]
    workflows: list[Workflow]
    classify_provider: str
    reply_provider: str
    system_prompt: str | None = None
    blocklist: Blocklist | None = None


@dataclass
class Settings:
    catch_up_on_start: bool = True
    debounce_ms: int = 200
    classify_body_limit: int = 2000
    reply_body_limit: int = 8000
    llm_retries: int = 1
    llm_timeout_seconds: int = 30
    data_dir: str = "/app/data"
    log_level: str = "info"
    mail_host: str = "mailserver"


@dataclass
class Defaults:
    classify_provider: str
    reply_provider: str
    system_prompt: str = "You are a helpful email assistant."
    blocklist: Blocklist = field(default_factory=Blocklist)


@dataclass
class Config:
    providers: dict[str, ProviderConfig]
    defaults: Defaults
    inboxes: list[InboxConfig]
    settings: Settings


@dataclass
class LoadResult:
    config: Config
    warnings: list[str]


def load_config(
    path: str | Path = "/app/config.yml", schema_path: str | Path | None = None
) -> LoadResult:
    config_path = Path(path)
    if not config_path.exists():
        raise ConfigError(f"Config file not found: {config_path}")

    raw = _load_yaml(config_path)
    interpolated, interpolation_errors = interpolate_env_vars(raw)

    errors: list[str] = []
    warnings: list[str] = []

    if interpolation_errors:
        errors.extend(interpolation_errors)

    schema = load_schema(schema_path)
    errors.extend(_validate_schema(interpolated, schema))

    if errors:
        raise ConfigError("\n".join(errors))

    config = _build_typed_config(interpolated, warnings, errors)

    if errors:
        raise ConfigError("\n".join(errors))

    return LoadResult(config=config, warnings=warnings)


def load_schema(schema_path: str | Path | None = None) -> dict[str, Any]:
    if schema_path is None:
        schema_path = _default_schema_path()
    schema_file = Path(schema_path)
    if not schema_file.exists():
        raise ConfigError(f"Schema file not found: {schema_file}")
    return json.loads(schema_file.read_text(encoding="utf-8"))


def schema_text(schema_path: str | Path | None = None) -> str:
    schema = load_schema(schema_path)
    return json.dumps(schema, indent=2, sort_keys=False)


def _default_schema_path() -> Path:
    candidates = [
        Path(__file__).with_name("schema.json"),
        Path(__file__).resolve().parents[2] / "schema.json",
        Path.cwd() / "schema.json",
        Path("/app/schema.json"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ConfigError("Root config must be a YAML mapping/object")
    return data


def _validate_schema(config_data: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    validator = jsonschema.Draft202012Validator(schema)
    errors: list[str] = []

    for error in sorted(
        validator.iter_errors(config_data), key=lambda err: list(err.path)
    ):
        path = ".".join(str(p) for p in error.path)
        path_prefix = path or "<root>"
        errors.append(f"{path_prefix}: {error.message}")

    return errors


def _build_typed_config(
    raw: dict[str, Any], warnings: list[str], errors: list[str]
) -> Config:
    providers: dict[str, ProviderConfig] = {}
    for name, provider in raw["providers"].items():
        providers[name] = ProviderConfig(
            name=name,
            type=provider["type"],
            model=provider["model"],
            api_key=provider["api_key"],
            base_url=provider.get("base_url"),
            timeout=int(
                provider.get(
                    "timeout", raw.get("settings", {}).get("llm_timeout_seconds", 30)
                )
            ),
            retries=int(
                provider.get("retries", raw.get("settings", {}).get("llm_retries", 1))
            ),
            http_referer=provider.get("http_referer"),
            x_title=provider.get("x_title"),
        )

    raw_defaults = raw["defaults"]
    defaults = Defaults(
        classify_provider=raw_defaults["classify_provider"],
        reply_provider=raw_defaults["reply_provider"],
        system_prompt=raw_defaults.get(
            "system_prompt", "You are a helpful email assistant."
        ),
        blocklist=Blocklist(
            from_patterns=list(
                raw_defaults.get("blocklist", {}).get("from_patterns", [])
            ),
            headers=list(raw_defaults.get("blocklist", {}).get("headers", [])),
        ),
    )

    if defaults.classify_provider not in providers:
        errors.append(
            f"defaults.classify_provider references undefined provider '{defaults.classify_provider}'"
        )
    if defaults.reply_provider not in providers:
        errors.append(
            f"defaults.reply_provider references undefined provider '{defaults.reply_provider}'"
        )

    settings_raw = raw.get("settings", {})
    settings = Settings(
        catch_up_on_start=settings_raw.get("catch_up_on_start", True),
        debounce_ms=int(settings_raw.get("debounce_ms", 200)),
        classify_body_limit=int(settings_raw.get("classify_body_limit", 2000)),
        reply_body_limit=int(settings_raw.get("reply_body_limit", 8000)),
        llm_retries=int(settings_raw.get("llm_retries", 1)),
        llm_timeout_seconds=int(settings_raw.get("llm_timeout_seconds", 30)),
        data_dir=settings_raw.get("data_dir", "/app/data"),
        log_level=settings_raw.get("log_level", "info"),
        mail_host=settings_raw.get("mail_host", "mailserver"),
    )

    inboxes: list[InboxConfig] = []
    seen_addresses: set[str] = set()

    for inbox_idx, raw_inbox in enumerate(raw["inboxes"]):
        address = raw_inbox["address"].lower()
        if address in seen_addresses:
            errors.append(
                f"inboxes[{inbox_idx}].address: duplicate inbox address {address}"
            )
            continue
        seen_addresses.add(address)

        classify_provider = raw_inbox.get(
            "classify_provider", defaults.classify_provider
        )
        reply_provider = raw_inbox.get("reply_provider", defaults.reply_provider)

        if classify_provider not in providers:
            errors.append(
                f"inboxes[{inbox_idx}].classify_provider references undefined provider '{classify_provider}'"
            )
        if reply_provider not in providers:
            errors.append(
                f"inboxes[{inbox_idx}].reply_provider references undefined provider '{reply_provider}'"
            )

        credentials = dict(raw_inbox.get("credentials", {}))
        if not credentials.get("password"):
            errors.append(f"inboxes[{inbox_idx}].credentials.password must be present")

        inbox_blocklist = raw_inbox.get("blocklist", {})
        merged_blocklist = Blocklist(
            from_patterns=defaults.blocklist.from_patterns
            + list(inbox_blocklist.get("from_patterns", [])),
            headers=defaults.blocklist.headers
            + list(inbox_blocklist.get("headers", [])),
        )

        inbox_prompt = raw_inbox.get("system_prompt", "")
        system_prompt = _merge_prompts(defaults.system_prompt, inbox_prompt)

        workflows = _parse_workflows(
            raw_inbox.get("workflows", []), inbox_idx, warnings
        )

        inboxes.append(
            InboxConfig(
                address=address,
                credentials=credentials,
                workflows=workflows,
                classify_provider=classify_provider,
                reply_provider=reply_provider,
                system_prompt=system_prompt,
                blocklist=merged_blocklist,
            )
        )

    return Config(
        providers=providers, defaults=defaults, inboxes=inboxes, settings=settings
    )


def _parse_workflows(
    raw_workflows: list[dict[str, Any]], inbox_idx: int, warnings: list[str]
) -> list[Workflow]:
    workflows: list[Workflow] = []
    first_default_idx: int | None = None
    fallback_idx: int | None = None

    for workflow_idx, wf in enumerate(raw_workflows):
        keywords_raw = wf.get("match", {}).get("keywords")
        keywords = None
        if isinstance(keywords_raw, dict):
            keywords = KeywordMatch(
                any=list(keywords_raw["any"]) if "any" in keywords_raw else None,
                all=list(keywords_raw["all"]) if "all" in keywords_raw else None,
            )

        action_raw = wf["action"]
        action = WorkflowAction(
            type=action_raw["type"],
            prompt=action_raw.get("prompt"),
            webhook=action_raw.get("webhook"),
            url=action_raw.get("url"),
            method=action_raw.get("method", "POST"),
            headers=action_raw.get("headers"),
            payload=action_raw.get("payload"),
            also_reply=bool(action_raw.get("also_reply", False)),
            also_webhook=bool(action_raw.get("also_webhook", False)),
            webhook_url=action_raw.get("webhook_url"),
        )

        workflow = Workflow(
            name=wf["name"],
            match=WorkflowMatch(intent=wf["match"]["intent"], keywords=keywords),
            action=action,
        )

        is_default = workflow.match.intent.lower() == "default"

        if is_default and first_default_idx is None:
            first_default_idx = workflow_idx

        if (
            first_default_idx is not None
            and workflow_idx > first_default_idx
            and not is_default
        ):
            warnings.append(
                f"inboxes[{inbox_idx}].workflows[{workflow_idx}] ({workflow.name}) is unreachable because a default workflow appears earlier"
            )

        if is_default:
            fallback_idx = workflow_idx

        if workflow.action.type == "reply" and not workflow.action.prompt:
            warnings.append(
                f"inboxes[{inbox_idx}].workflows[{workflow_idx}] ({workflow.name}): reply action has no prompt"
            )

        workflows.append(workflow)

    if fallback_idx is None:
        warnings.append(
            f"inboxes[{inbox_idx}] has no fallback workflow; auto-adding fallback ignore workflow"
        )
        workflows.append(
            Workflow(
                name="fallback",
                match=WorkflowMatch(intent="default", keywords=None),
                action=WorkflowAction(type="ignore"),
            )
        )
        fallback_idx = len(workflows) - 1

    if fallback_idx != len(workflows) - 1:
        warnings.append(
            f"inboxes[{inbox_idx}] fallback workflow is not last; workflows after it are unreachable"
        )

    return workflows


def _merge_prompts(global_prompt: str, inbox_prompt: str | None) -> str:
    if not inbox_prompt:
        return global_prompt
    if not global_prompt:
        return inbox_prompt
    return f"{global_prompt.rstrip()}\n{inbox_prompt.lstrip()}"
