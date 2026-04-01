from __future__ import annotations

import argparse
import email.utils
import json
import logging
import os
import sys
import time
from pathlib import Path

from rich.console import Console

from .core.classifier import classify
from .config import ConfigError, ConfigManager, load_config, schema_text
from .core.parser import parse
from .core.watcher import build_provider, maildir_new_path, run as run_watcher
from .core.workflows import execute
from .utils.logging import setup_logging

logger = logging.getLogger(__name__)
console = Console()

DEFAULT_CONFIG = os.environ.get("MAILAGENT_CONFIG", "/app/config.yml")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    command = args.command or "run"
    config_path = getattr(args, "config", DEFAULT_CONFIG)
    verbose = getattr(args, "verbose", False)

    if command == "schema":
        print(schema_text())
        return 0

    if command == "validate":
        return _cmd_validate(config_path, verbose)

    if command == "test":
        subcommand = getattr(args, "test_command", None)
        if subcommand is None:
            # Legacy: mailagent test <eml_path>
            eml_path = getattr(args, "eml_path", None)
            if eml_path:
                return _cmd_test_eml(Path(eml_path), config_path, verbose)
            Console(stderr=True).print("[red]Usage:[/] mailagent test {dry|live|quick} [options]")
            return 2
        if subcommand == "dry":
            return _cmd_test_dry(args)
        if subcommand == "live":
            return _cmd_test_live(args)
        if subcommand == "quick":
            return _cmd_test_quick(args)
        # Fallback: treat subcommand as eml path for backwards compat
        return _cmd_test_eml(Path(subcommand), config_path, verbose)

    if command == "run":
        return _cmd_run(config_path, verbose)

    if command == "serve":
        return _cmd_serve(
            config_path,
            verbose,
            host=getattr(args, "host", "0.0.0.0"),
            port=getattr(args, "port", 8000),
            api_keys_path=getattr(args, "api_keys", None),
            dms_config_dir=getattr(args, "dms_config", None),
        )

    if command == "api-key":
        return _cmd_api_key(args)

    parser.error(f"Unknown command: {command}")
    return 2


def _build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "-c", "--config", default=DEFAULT_CONFIG, help="Config file path"
    )
    common.add_argument(
        "-v", "--verbose", action="store_true", help="Enable debug logging"
    )

    parser = argparse.ArgumentParser(
        prog="mailagent", description="Your inbox, on autopilot."
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("run", parents=[common], help="Start the mail agent daemon")
    subparsers.add_parser(
        "validate", parents=[common], help="Validate the config file and exit"
    )

    # ── test command with subcommands ──
    test_parser = subparsers.add_parser(
        "test", parents=[common], help="Test email workflows"
    )
    test_sub = test_parser.add_subparsers(dest="test_command")

    # mailagent test dry
    dry_parser = test_sub.add_parser("dry", parents=[common], help="Dry-run tests (classification only)")
    dry_parser.add_argument(
        "-t", "--tests", default="./mailagent.test.yml", help="Test file path"
    )
    dry_parser.add_argument(
        "-f", "--filter", dest="filter_name", default=None,
        help="Run only tests matching this name (substring)",
    )
    dry_parser.add_argument(
        "--no-generate", action="store_true",
        help="Skip generate/generate_batch tests",
    )

    # mailagent test live
    live_parser = test_sub.add_parser("live", parents=[common], help="Full end-to-end tests via Inbucket")
    live_parser.add_argument(
        "-t", "--tests", default="./mailagent.test.yml", help="Test file path"
    )
    live_parser.add_argument(
        "-f", "--filter", dest="filter_name", default=None,
        help="Run only tests matching this name",
    )
    live_parser.add_argument(
        "--keep", action="store_true",
        help="Don't tear down Inbucket after tests",
    )
    live_parser.add_argument(
        "--inbucket-url", default=None,
        help="Use an existing Inbucket instance",
    )
    live_parser.add_argument(
        "--timeout", type=int, default=30,
        help="Max seconds to wait for pipeline processing",
    )

    # mailagent test quick
    quick_parser = test_sub.add_parser("quick", parents=[common], help="Ad-hoc single email test")
    quick_parser.add_argument("--inbox", default=None, help="Target inbox address")
    quick_parser.add_argument("--from", dest="from_addr", default=None, help="Sender address")
    quick_parser.add_argument("--subject", default=None, help="Email subject")
    quick_parser.add_argument("--body", default=None, help="Email body (or - for stdin)")
    quick_parser.add_argument("--describe", default=None, help="Generate email from description")
    quick_parser.add_argument("--live", action="store_true", help="Run through full pipeline via Inbucket")

    # Legacy positional arg for backwards compat: mailagent test <eml_path>
    test_parser.add_argument("eml_path", nargs="?", default=None, help=argparse.SUPPRESS)

    subparsers.add_parser(
        "schema", parents=[common], help="Print JSON Schema to stdout"
    )

    # ── serve command ──
    serve_parser = subparsers.add_parser(
        "serve", parents=[common], help="Start the REST API server"
    )
    serve_parser.add_argument(
        "--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)"
    )
    serve_parser.add_argument(
        "--port", type=int, default=8000, help="Bind port (default: 8000)"
    )
    serve_parser.add_argument(
        "--api-keys", default=None, help="Path to API keys file"
    )
    serve_parser.add_argument(
        "--dms-config", default=None,
        help="Path to docker-mailserver config dir for provisioning",
    )

    # ── api-key command ──
    apikey_parser = subparsers.add_parser(
        "api-key", help="Manage API keys"
    )
    apikey_sub = apikey_parser.add_subparsers(dest="apikey_command")

    create_key = apikey_sub.add_parser("create", help="Create a new API key")
    create_key.add_argument("--name", default="default", help="Key name")
    create_key.add_argument("--api-keys", default=None, help="Path to API keys file")

    list_key = apikey_sub.add_parser("list", help="List API keys")
    list_key.add_argument("--api-keys", default=None, help="Path to API keys file")

    revoke_key = apikey_sub.add_parser("revoke", help="Revoke an API key")
    revoke_key.add_argument("hash_prefix", help="Hash prefix of the key to revoke")
    revoke_key.add_argument("--api-keys", default=None, help="Path to API keys file")

    return parser


def _cmd_run(config_path: str, verbose: bool) -> int:
    err = Console(stderr=True)
    try:
        load_result = load_config(config_path)
    except ConfigError as exc:
        err.print(f"[red]Config validation failed:[/]\n{exc}")
        return 1

    setup_logging(
        verbose=verbose,
        level=load_result.config.settings.log_level,
    )

    for warning in load_result.warnings:
        logger.warning(warning)

    while True:
        try:
            run_watcher(load_result.config, config_path=config_path)
            return 0
        except KeyboardInterrupt:
            logger.info("Interrupted, exiting")
            return 0
        except Exception as exc:
            logger.exception("Watcher crashed: %s; restarting in 5s", exc)
            time.sleep(5)


def _cmd_serve(
    config_path: str,
    verbose: bool,
    host: str = "0.0.0.0",
    port: int = 8000,
    api_keys_path: str | None = None,
    dms_config_dir: str | None = None,
) -> int:
    err = Console(stderr=True)
    try:
        load_result = load_config(config_path)
    except ConfigError as exc:
        err.print(f"[red]Config validation failed:[/]\n{exc}")
        return 1

    setup_logging(verbose=verbose, level=load_result.config.settings.log_level)

    for warning in load_result.warnings:
        logger.warning(warning)

    try:
        import uvicorn
    except ImportError:
        err.print(
            "[red]Missing API dependencies.[/] Install with: "
            "pip install docker-mailagent[api]"
        )
        return 1

    from .api import create_app
    from .provisioner import Provisioner

    cm = ConfigManager(load_result.config, config_path)

    provisioner = None
    if dms_config_dir:
        provisioner = Provisioner(dms_config_dir)
        if provisioner.available:
            logger.info("Provisioner enabled: %s", dms_config_dir)
        else:
            logger.warning("DMS config dir not found: %s", dms_config_dir)
            provisioner = None

    app = create_app(cm, api_keys_path=api_keys_path, provisioner=provisioner)
    console.print(f"[green]Starting API server on {host}:{port}[/]")
    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0


def _cmd_api_key(args: argparse.Namespace) -> int:
    from .api.auth import create_api_key, list_api_keys, revoke_api_key

    sub = getattr(args, "apikey_command", None)
    api_keys_path = getattr(args, "api_keys", None)

    if sub == "create":
        key = create_api_key(api_keys_path=api_keys_path, name=args.name)
        console.print(f"[green]API key created:[/] {key}")
        console.print("[dim]Store this key securely — it cannot be retrieved later.[/]")
        return 0

    if sub == "list":
        keys = list_api_keys(api_keys_path=api_keys_path)
        if not keys:
            console.print("[dim]No API keys found.[/]")
            return 0
        for k in keys:
            console.print(
                f"  {k['hash_prefix']}…  name={k['name']}  created={k['created_at']}"
            )
        return 0

    if sub == "revoke":
        ok = revoke_api_key(args.hash_prefix, api_keys_path=api_keys_path)
        if ok:
            console.print("[green]Key revoked.[/]")
        else:
            console.print("[red]No key found with that prefix.[/]")
            return 1
        return 0

    Console(stderr=True).print("[red]Usage:[/] mailagent api-key {create|list|revoke}")
    return 2


def _cmd_validate(config_path: str, verbose: bool) -> int:
    err = Console(stderr=True)
    try:
        load_result = load_config(config_path)
    except ConfigError as exc:
        err.print(f"[red]Config validation failed:[/]\n{exc}")
        return 1

    config = load_result.config
    setup_logging(verbose=verbose, level=config.settings.log_level)
    for warning in load_result.warnings:
        console.print(f"[yellow]Warning:[/] {warning}")

    for inbox in config.inboxes:
        watch_path = maildir_new_path(inbox.address)
        if not watch_path.exists():
            console.print(f"[yellow]Warning:[/] maildir does not exist for {inbox.address}: {watch_path}")

    console.print("[green]Config is valid[/]")
    return 0


def _cmd_test_eml(eml_path: Path, config_path: str, verbose: bool) -> int:
    """Legacy: dry-run a single .eml file through the pipeline."""
    err = Console(stderr=True)
    if not eml_path.exists():
        err.print(f"[red]Input file not found:[/] {eml_path}")
        return 1

    try:
        load_result = load_config(config_path)
    except ConfigError as exc:
        err.print(f"[red]Config validation failed:[/]\n{exc}")
        return 1

    config = load_result.config
    setup_logging(verbose=verbose, level=config.settings.log_level)
    parsed = parse(eml_path, truncate_at=config.settings.classify_body_limit)
    inbox = _select_inbox(config, parsed.to_addr)

    if inbox is None:
        err.print("[red]No inboxes configured[/]")
        return 1

    classify_provider = build_provider(config, inbox.classify_provider)
    reply_provider = build_provider(config, inbox.reply_provider)

    result = classify(
        email=parsed,
        workflows=inbox.workflows,
        provider=classify_provider,
        system_prompt=inbox.system_prompt or "You are a helpful email assistant.",
    )

    action_preview = execute(
        workflow_name=result.workflow_name,
        parsed_email=parsed,
        inbox=inbox,
        config=config,
        reply_provider=reply_provider,
        dry_run=True,
    )

    console.print("[bold]Parsed email[/]")
    console.print(f"  file: {parsed.filepath}")
    console.print(f"  from: {parsed.from_addr}")
    console.print(f"  to: {parsed.to_addr}")
    console.print(f"  subject: {parsed.subject}")
    console.print()
    console.print("[bold]Classification[/]")
    console.print(f"  inbox: {inbox.address}")
    console.print(f"  workflow: [cyan]{result.workflow_name}[/]")
    console.print(f"  method: {result.method}")
    if result.confidence is not None:
        console.print(f"  confidence: {result.confidence}")
    console.print()
    console.print("[bold]Action preview[/]")
    console.print(json.dumps(action_preview, indent=2, sort_keys=True))

    return 0


def _cmd_test_dry(args: argparse.Namespace) -> int:
    config_path = args.config
    verbose = args.verbose
    setup_logging(verbose=verbose)

    from .testing.runner import load_test_config, run_dry

    try:
        test_config = load_test_config(args.tests)
    except (FileNotFoundError, ValueError) as exc:
        Console(stderr=True).print(f"[red]Error loading test file:[/] {exc}")
        return 1

    resolved_config = test_config.config_path
    if not Path(resolved_config).is_absolute():
        resolved_config = str(Path(args.tests).parent / resolved_config)

    try:
        return run_dry(
            test_config=test_config,
            config_path=config_path if config_path != DEFAULT_CONFIG else resolved_config,
            filter_name=args.filter_name,
            no_generate=args.no_generate,
            verbose=verbose,
        )
    except ConfigError as exc:
        Console(stderr=True).print(f"[red]Config validation failed:[/]\n{exc}")
        return 1


def _cmd_test_live(args: argparse.Namespace) -> int:
    config_path = args.config
    verbose = args.verbose
    setup_logging(verbose=verbose)

    from .testing.runner import load_test_config, run_live

    try:
        test_config = load_test_config(args.tests)
    except (FileNotFoundError, ValueError) as exc:
        Console(stderr=True).print(f"[red]Error loading test file:[/] {exc}")
        return 1

    resolved_config = test_config.config_path
    if not Path(resolved_config).is_absolute():
        resolved_config = str(Path(args.tests).parent / resolved_config)

    try:
        return run_live(
            test_config=test_config,
            config_path=config_path if config_path != DEFAULT_CONFIG else resolved_config,
            filter_name=args.filter_name,
            keep=args.keep,
            inbucket_url=args.inbucket_url,
            timeout_seconds=args.timeout,
            verbose=verbose,
        )
    except ConfigError as exc:
        Console(stderr=True).print(f"[red]Config validation failed:[/]\n{exc}")
        return 1


def _cmd_test_quick(args: argparse.Namespace) -> int:
    config_path = args.config
    verbose = args.verbose
    setup_logging(verbose=verbose)

    from .testing.runner import run_quick

    body = args.body
    if body == "-":
        body = sys.stdin.read()

    try:
        return run_quick(
            config_path=config_path,
            inbox_address=args.inbox,
            from_addr=args.from_addr,
            subject=args.subject,
            body=body,
            describe=args.describe,
            live=args.live,
            verbose=verbose,
        )
    except ConfigError as exc:
        Console(stderr=True).print(f"[red]Config validation failed:[/]\n{exc}")
        return 1


def _select_inbox(config, to_addr: str):
    if not config.inboxes:
        return None

    candidates = {
        addr.lower() for _, addr in email.utils.getaddresses([to_addr]) if addr
    }
    for inbox in config.inboxes:
        if inbox.address.lower() in candidates:
            return inbox
    logger.warning(
        "No inbox matches To address %r; defaulting to %s",
        to_addr, config.inboxes[0].address,
    )
    return config.inboxes[0]


if __name__ == "__main__":
    raise SystemExit(main())
