from __future__ import annotations

import fcntl
import json
import threading
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
    name: str | None = None
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
    max_thread_replies: int = 3
    thread_context_limit: int = 3000
    thread_history_max: int = 5
    api_port: int = 8000
    api_enabled: bool = True
    dms_config_dir: str = "/app/dms-config"


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
        max_thread_replies=int(settings_raw.get("max_thread_replies", 3)),
        thread_context_limit=int(settings_raw.get("thread_context_limit", 3000)),
        thread_history_max=int(settings_raw.get("thread_history_max", 5)),
        api_port=int(settings_raw.get("api_port", 8000)),
        api_enabled=settings_raw.get("api_enabled", True),
        dms_config_dir=settings_raw.get("dms_config_dir", "/app/dms-config"),
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
                name=raw_inbox.get("name"),
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


class ConfigManager:
    """Thread-safe wrapper around Config with YAML persistence.

    All reads/writes go through a lock so the watcher and API
    threads can safely share the same config state.
    """

    def __init__(self, config: Config, config_path: str | Path, warnings: list[str] | None = None):
        self._lock = threading.RLock()
        self._config = config
        self._config_path = Path(config_path)
        self._warnings = list(warnings or [])

    @property
    def config(self) -> Config:
        with self._lock:
            return self._config

    @property
    def warnings(self) -> list[str]:
        with self._lock:
            return list(self._warnings)

    def get_inbox(self, address: str) -> InboxConfig | None:
        with self._lock:
            address_lower = address.lower()
            for inbox in self._config.inboxes:
                if inbox.address.lower() == address_lower:
                    return inbox
            return None

    def get_provider(self, name: str) -> ProviderConfig | None:
        with self._lock:
            return self._config.providers.get(name)

    def add_inbox(self, inbox: InboxConfig) -> None:
        with self._lock:
            address_lower = inbox.address.lower()
            for existing in self._config.inboxes:
                if existing.address.lower() == address_lower:
                    raise ConfigError(f"Inbox already exists: {inbox.address}")
            self._config.inboxes.append(inbox)
            self._persist()

    def update_inbox(self, address: str, inbox: InboxConfig) -> None:
        with self._lock:
            address_lower = address.lower()
            for i, existing in enumerate(self._config.inboxes):
                if existing.address.lower() == address_lower:
                    self._config.inboxes[i] = inbox
                    self._persist()
                    return
            raise ConfigError(f"Inbox not found: {address}")

    def remove_inbox(self, address: str) -> None:
        with self._lock:
            address_lower = address.lower()
            for i, existing in enumerate(self._config.inboxes):
                if existing.address.lower() == address_lower:
                    self._config.inboxes.pop(i)
                    self._persist()
                    return
            raise ConfigError(f"Inbox not found: {address}")

    def add_provider(self, name: str, provider: ProviderConfig) -> None:
        with self._lock:
            if name in self._config.providers:
                raise ConfigError(f"Provider already exists: {name}")
            self._config.providers[name] = provider
            self._persist()

    def update_provider(self, name: str, provider: ProviderConfig) -> None:
        with self._lock:
            if name not in self._config.providers:
                raise ConfigError(f"Provider not found: {name}")
            self._config.providers[name] = provider
            self._persist()

    def remove_provider(self, name: str) -> None:
        with self._lock:
            if name not in self._config.providers:
                raise ConfigError(f"Provider not found: {name}")
            # Check if any inbox references this provider
            for inbox in self._config.inboxes:
                if inbox.classify_provider == name or inbox.reply_provider == name:
                    raise ConfigError(
                        f"Cannot remove provider '{name}': still referenced by inbox '{inbox.address}'"
                    )
            if self._config.defaults.classify_provider == name:
                raise ConfigError(f"Cannot remove provider '{name}': used as default classify_provider")
            if self._config.defaults.reply_provider == name:
                raise ConfigError(f"Cannot remove provider '{name}': used as default reply_provider")
            del self._config.providers[name]
            self._persist()

    def _persist(self) -> None:
        """Write current config state back to YAML with file locking."""
        raw = _config_to_raw(self._config)
        yaml_str = yaml.dump(raw, default_flow_style=False, sort_keys=False, allow_unicode=True)
        with open(self._config_path, "w", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                f.write(yaml_str)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def _config_to_raw(config: Config) -> dict[str, Any]:
    """Serialize a Config back to the raw dict format for YAML output."""
    providers: dict[str, Any] = {}
    for name, p in config.providers.items():
        entry: dict[str, Any] = {"type": p.type, "model": p.model, "api_key": p.api_key}
        if p.base_url:
            entry["base_url"] = p.base_url
        if p.timeout != 30:
            entry["timeout"] = p.timeout
        if p.retries != 1:
            entry["retries"] = p.retries
        if p.http_referer:
            entry["http_referer"] = p.http_referer
        if p.x_title:
            entry["x_title"] = p.x_title
        providers[name] = entry

    defaults: dict[str, Any] = {
        "classify_provider": config.defaults.classify_provider,
        "reply_provider": config.defaults.reply_provider,
    }
    if config.defaults.system_prompt != "You are a helpful email assistant.":
        defaults["system_prompt"] = config.defaults.system_prompt
    if config.defaults.blocklist.from_patterns or config.defaults.blocklist.headers:
        bl: dict[str, Any] = {}
        if config.defaults.blocklist.from_patterns:
            bl["from_patterns"] = config.defaults.blocklist.from_patterns
        if config.defaults.blocklist.headers:
            bl["headers"] = config.defaults.blocklist.headers
        defaults["blocklist"] = bl

    inboxes: list[dict[str, Any]] = []
    for inbox in config.inboxes:
        entry = {
            "address": inbox.address,
            "credentials": dict(inbox.credentials),
            "workflows": [_workflow_to_raw(w) for w in inbox.workflows],
        }
        if inbox.name:
            entry["name"] = inbox.name
        if inbox.classify_provider != config.defaults.classify_provider:
            entry["classify_provider"] = inbox.classify_provider
        if inbox.reply_provider != config.defaults.reply_provider:
            entry["reply_provider"] = inbox.reply_provider
        if inbox.system_prompt:
            entry["system_prompt"] = inbox.system_prompt
        if inbox.blocklist and (inbox.blocklist.from_patterns or inbox.blocklist.headers):
            bl = {}
            if inbox.blocklist.from_patterns:
                bl["from_patterns"] = inbox.blocklist.from_patterns
            if inbox.blocklist.headers:
                bl["headers"] = inbox.blocklist.headers
            entry["blocklist"] = bl
        inboxes.append(entry)

    raw: dict[str, Any] = {
        "providers": providers,
        "defaults": defaults,
        "inboxes": inboxes,
    }

    settings = _settings_to_raw(config.settings)
    if settings:
        raw["settings"] = settings

    return raw


def _workflow_to_raw(w: Workflow) -> dict[str, Any]:
    match: dict[str, Any] = {"intent": w.match.intent}
    if w.match.keywords:
        kw: dict[str, Any] = {}
        if w.match.keywords.any:
            kw["any"] = w.match.keywords.any
        if w.match.keywords.all:
            kw["all"] = w.match.keywords.all
        match["keywords"] = kw

    action: dict[str, Any] = {"type": w.action.type}
    if w.action.prompt:
        action["prompt"] = w.action.prompt
    if w.action.webhook:
        action["webhook"] = w.action.webhook
    if w.action.url:
        action["url"] = w.action.url
    if w.action.method != "POST":
        action["method"] = w.action.method
    if w.action.headers:
        action["headers"] = w.action.headers
    if w.action.payload:
        action["payload"] = w.action.payload
    if w.action.also_reply:
        action["also_reply"] = True
    if w.action.also_webhook:
        action["also_webhook"] = True
    if w.action.webhook_url:
        action["webhook_url"] = w.action.webhook_url

    return {"name": w.name, "match": match, "action": action}


def _settings_to_raw(s: Settings) -> dict[str, Any]:
    raw: dict[str, Any] = {}
    defaults = Settings()
    if s.catch_up_on_start != defaults.catch_up_on_start:
        raw["catch_up_on_start"] = s.catch_up_on_start
    if s.debounce_ms != defaults.debounce_ms:
        raw["debounce_ms"] = s.debounce_ms
    if s.classify_body_limit != defaults.classify_body_limit:
        raw["classify_body_limit"] = s.classify_body_limit
    if s.reply_body_limit != defaults.reply_body_limit:
        raw["reply_body_limit"] = s.reply_body_limit
    if s.llm_retries != defaults.llm_retries:
        raw["llm_retries"] = s.llm_retries
    if s.llm_timeout_seconds != defaults.llm_timeout_seconds:
        raw["llm_timeout_seconds"] = s.llm_timeout_seconds
    if s.data_dir != defaults.data_dir:
        raw["data_dir"] = s.data_dir
    if s.log_level != defaults.log_level:
        raw["log_level"] = s.log_level
    if s.mail_host != defaults.mail_host:
        raw["mail_host"] = s.mail_host
    if s.max_thread_replies != defaults.max_thread_replies:
        raw["max_thread_replies"] = s.max_thread_replies
    if s.thread_context_limit != defaults.thread_context_limit:
        raw["thread_context_limit"] = s.thread_context_limit
    if s.thread_history_max != defaults.thread_history_max:
        raw["thread_history_max"] = s.thread_history_max
    if s.api_port != defaults.api_port:
        raw["api_port"] = s.api_port
    if s.api_enabled != defaults.api_enabled:
        raw["api_enabled"] = s.api_enabled
    if s.dms_config_dir != defaults.dms_config_dir:
        raw["dms_config_dir"] = s.dms_config_dir
    return raw
