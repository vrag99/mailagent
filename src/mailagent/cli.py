from __future__ import annotations

import argparse
import email.utils
import json
import logging
import os
import sys
import time
from pathlib import Path

from .classifier import classify
from .config import ConfigError, load_config, schema_text
from .parser import parse
from .watcher import build_provider, maildir_new_path, run as run_watcher
from .workflows import execute
from .utils.logging import setup_logging

logger = logging.getLogger(__name__)

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
            print("Usage: mailagent test {dry|live|quick} [options]", file=sys.stderr)
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

    return parser


def _cmd_run(config_path: str, verbose: bool) -> int:
    try:
        load_result = load_config(config_path)
    except ConfigError as exc:
        print(f"Config validation failed:\n{exc}", file=sys.stderr)
        return 1

    setup_logging(
        verbose=verbose,
        level=load_result.config.settings.log_level,
    )

    for warning in load_result.warnings:
        logger.warning(warning)

    while True:
        try:
            run_watcher(load_result.config)
            return 0
        except KeyboardInterrupt:
            logger.info("Interrupted, exiting")
            return 0
        except Exception as exc:
            logger.exception("Watcher crashed: %s; restarting in 5s", exc)
            time.sleep(5)


def _cmd_validate(config_path: str, verbose: bool) -> int:
    try:
        load_result = load_config(config_path)
    except ConfigError as exc:
        print(f"Config validation failed:\n{exc}", file=sys.stderr)
        return 1

    config = load_result.config
    setup_logging(verbose=verbose, level=config.settings.log_level)
    for warning in load_result.warnings:
        print(f"Warning: {warning}")

    for inbox in config.inboxes:
        watch_path = maildir_new_path(inbox.address)
        if not watch_path.exists():
            print(f"Warning: maildir does not exist for {inbox.address}: {watch_path}")

    print("Config is valid")
    return 0


def _cmd_test_eml(eml_path: Path, config_path: str, verbose: bool) -> int:
    """Legacy: dry-run a single .eml file through the pipeline."""
    if not eml_path.exists():
        print(f"Input file not found: {eml_path}", file=sys.stderr)
        return 1

    try:
        load_result = load_config(config_path)
    except ConfigError as exc:
        print(f"Config validation failed:\n{exc}", file=sys.stderr)
        return 1

    config = load_result.config
    setup_logging(verbose=verbose, level=config.settings.log_level)
    parsed = parse(eml_path, truncate_at=config.settings.classify_body_limit)
    inbox = _select_inbox(config, parsed.to_addr)

    if inbox is None:
        print("No inboxes configured", file=sys.stderr)
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

    print("Parsed email")
    print(f"  file: {parsed.filepath}")
    print(f"  from: {parsed.from_addr}")
    print(f"  to: {parsed.to_addr}")
    print(f"  subject: {parsed.subject}")
    print()
    print("Classification")
    print(f"  inbox: {inbox.address}")
    print(f"  workflow: {result.workflow_name}")
    print(f"  method: {result.method}")
    print()
    print("Action preview")
    print(json.dumps(action_preview, indent=2, sort_keys=True))

    return 0


def _cmd_test_dry(args: argparse.Namespace) -> int:
    config_path = args.config
    verbose = args.verbose
    setup_logging(verbose=verbose)

    from .testing.runner import load_test_config, run_dry

    try:
        test_config = load_test_config(args.tests)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error loading test file: {exc}", file=sys.stderr)
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
        print(f"Config validation failed:\n{exc}", file=sys.stderr)
        return 1


def _cmd_test_live(args: argparse.Namespace) -> int:
    config_path = args.config
    verbose = args.verbose
    setup_logging(verbose=verbose)

    from .testing.runner import load_test_config, run_live

    try:
        test_config = load_test_config(args.tests)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error loading test file: {exc}", file=sys.stderr)
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
        print(f"Config validation failed:\n{exc}", file=sys.stderr)
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
        print(f"Config validation failed:\n{exc}", file=sys.stderr)
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
