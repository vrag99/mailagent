"""Test orchestrator for dry-run and live modes."""

from __future__ import annotations

import email as email_mod
import email.utils
import logging
import smtplib
import time
from dataclasses import dataclass, field
from email.message import Message
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

import yaml

from ..core.classifier import classify
from ..config import Config, InboxConfig, LoadResult, load_config
from ..core.parser import ParsedEmail
from ..providers import BaseProvider
from ..core.watcher import build_provider
from ..core.workflows import _block_reason
from .generator import GeneratedEmail, generate_batch, generate_email
from .reporter import TestResult, print_report
from .webhook_capture import WebhookCaptureServer

logger = logging.getLogger(__name__)


# ── Test config loading ──────────────────────────────────────────


@dataclass
class TestExpect:
    workflow: str | None = None
    action: str | None = None
    blocked: bool = False


@dataclass
class TestCase:
    name: str
    # Exactly one of the three source types:
    generate: dict[str, Any] | None = None
    generate_batch: dict[str, Any] | None = None
    email: dict[str, Any] | None = None
    expect: TestExpect | None = None


@dataclass
class TestConfig:
    config_path: str
    inbox: str
    generator: dict[str, Any] | None
    tests: list[TestCase]


def load_test_config(path: str | Path) -> TestConfig:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Test file not found: {p}")

    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Test file must be a YAML mapping")

    tests: list[TestCase] = []
    for t in raw.get("tests", []):
        expect_raw = t.get("expect")
        expect = None
        if expect_raw:
            expect = TestExpect(
                workflow=expect_raw.get("workflow"),
                action=expect_raw.get("action"),
                blocked=bool(expect_raw.get("blocked", False)),
            )
        tests.append(
            TestCase(
                name=t["name"],
                generate=t.get("generate"),
                generate_batch=t.get("generate_batch"),
                email=t.get("email"),
                expect=expect,
            )
        )

    return TestConfig(
        config_path=raw.get("config", "./mailagent.yml"),
        inbox=raw.get("inbox", ""),
        generator=raw.get("generator"),
        tests=tests,
    )


# ── Helpers ──────────────────────────────────────────────────────


def _build_parsed_email(
    from_addr: str,
    subject: str,
    body: str,
    to_addr: str,
    headers: dict[str, str] | None = None,
) -> ParsedEmail:
    """Construct a ParsedEmail from raw fields (no .eml file needed)."""
    msg = MIMEMultipart()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg["Date"] = email.utils.formatdate(localtime=True)
    msg["Message-ID"] = email.utils.make_msgid()
    if headers:
        for k, v in headers.items():
            msg[k] = v
    msg.attach(MIMEText(body, "plain", "utf-8"))

    _, from_email = email.utils.parseaddr(from_addr)

    return ParsedEmail(
        filepath="<test>",
        from_addr=from_addr,
        from_email=from_email.lower(),
        to_addr=to_addr,
        subject=subject,
        date=msg["Date"],
        message_id=msg["Message-ID"],
        in_reply_to=None,
        references=None,
        body_plain=body,
        body_truncated=body[:2000],
        raw_msg=msg,
    )


def _find_inbox(config: Config, address: str) -> InboxConfig:
    addr_lower = address.lower()
    for inbox in config.inboxes:
        if inbox.address.lower() == addr_lower:
            return inbox
    if config.inboxes:
        return config.inboxes[0]
    raise ValueError("No inboxes configured")


def _build_generator_provider(
    gen_cfg: dict[str, Any] | None,
    main_config: Config,
) -> BaseProvider:
    """Build a provider for email generation from the generator config."""
    if not gen_cfg:
        raise ValueError("No generator configured and test cases require email generation")

    # Reference to an existing provider
    if "provider" in gen_cfg:
        return build_provider(main_config, gen_cfg["provider"])

    # Inline provider definition
    from ..providers import get_provider

    return get_provider(
        gen_cfg["type"],
        model=gen_cfg["model"],
        api_key=gen_cfg["api_key"],
        base_url=gen_cfg.get("base_url"),
        timeout=gen_cfg.get("timeout", 30),
        retries=gen_cfg.get("retries", 1),
    )


def _check_blocked(parsed: ParsedEmail, inbox: InboxConfig) -> str | None:
    return _block_reason(parsed, inbox)


def _classify_and_match(
    parsed: ParsedEmail,
    inbox: InboxConfig,
    config: Config,
    classify_provider: BaseProvider,
) -> tuple[str, str, str]:
    """Returns (workflow_name, method, action_type)."""
    result = classify(
        email=parsed,
        workflows=inbox.workflows,
        provider=classify_provider,
        system_prompt=inbox.system_prompt or "You are a helpful email assistant.",
    )
    # Find the action type
    action_type = "unknown"
    for wf in inbox.workflows:
        if wf.name == result.workflow_name:
            action_type = wf.action.type
            break
        if wf.match.intent.lower() == "default" and result.workflow_name == "fallback":
            action_type = wf.action.type
            break

    return result.workflow_name, result.method, action_type


# ── Dry-run runner ───────────────────────────────────────────────


def run_dry(
    test_config: TestConfig,
    config_path: str,
    filter_name: str | None = None,
    no_generate: bool = False,
    verbose: bool = False,
) -> int:
    load_result = load_config(config_path)
    config = load_result.config

    inbox = _find_inbox(config, test_config.inbox)
    classify_provider = build_provider(config, inbox.classify_provider)

    gen_provider: BaseProvider | None = None
    needs_gen = any(
        tc.generate or tc.generate_batch
        for tc in test_config.tests
    )
    if needs_gen and not no_generate:
        gen_provider = _build_generator_provider(test_config.generator, config)

    results: list[TestResult] = []

    for tc in test_config.tests:
        if filter_name and filter_name.lower() not in tc.name.lower():
            continue
        if no_generate and (tc.generate or tc.generate_batch):
            continue

        result = _run_dry_case(tc, inbox, config, classify_provider, gen_provider, verbose)
        results.append(result)

    print_report("dry", inbox.address, results)
    return 0 if all(r.passed for r in results) else 1


def _run_dry_case(
    tc: TestCase,
    inbox: InboxConfig,
    config: Config,
    classify_provider: BaseProvider,
    gen_provider: BaseProvider | None,
    verbose: bool,
) -> TestResult:
    details: list[str] = []

    # ── Generate or construct emails ──
    if tc.generate:
        if gen_provider is None:
            return TestResult(name=tc.name, passed=False, details=["No generator provider available"])
        try:
            gen = generate_email(
                gen_provider,
                tc.generate["description"],
                from_override=tc.generate.get("from"),
            )
        except Exception as exc:
            return TestResult(name=tc.name, passed=False, details=[f"Generation failed: {exc}"])
        emails = [gen]
        details.append(f'Generated: "{gen.subject}" from {gen.from_addr}')

    elif tc.generate_batch:
        if gen_provider is None:
            return TestResult(name=tc.name, passed=False, details=["No generator provider available"])
        try:
            emails_gen = generate_batch(
                gen_provider,
                tc.generate_batch["description"],
                tc.generate_batch.get("count", 5),
            )
        except Exception as exc:
            return TestResult(name=tc.name, passed=False, details=[f"Batch generation failed: {exc}"])
        emails = emails_gen
        details.append(f"Generated {len(emails)} emails")

    elif tc.email:
        emails = [
            GeneratedEmail(
                from_addr=tc.email["from"],
                subject=tc.email["subject"],
                body=tc.email.get("body", ""),
            )
        ]
        details.append(f'Email: "{tc.email["subject"]}" from {tc.email["from"]}')

    else:
        return TestResult(name=tc.name, passed=False, details=["No email source defined"])

    # ── Batch handling ──
    if tc.generate_batch:
        sub_results: list[TestResult] = []
        for gen_email in emails:
            parsed = _build_parsed_email(
                from_addr=gen_email.from_addr,
                subject=gen_email.subject,
                body=gen_email.body,
                to_addr=inbox.address,
            )
            sub = _classify_single(parsed, tc, inbox, config, classify_provider, verbose)
            sub_results.append(sub)

        all_passed = all(s.passed for s in sub_results)
        passed_count = sum(1 for s in sub_results if s.passed)
        details[0] = f"{tc.name} [{passed_count}/{len(sub_results)} passed]"
        return TestResult(
            name=tc.name,
            passed=all_passed,
            details=details,
            sub_results=sub_results,
        )

    # ── Single email ──
    email_data = emails[0]
    parsed = _build_parsed_email(
        from_addr=email_data.from_addr,
        subject=email_data.subject,
        body=email_data.body,
        to_addr=inbox.address,
        headers=tc.email.get("headers") if tc.email else None,
    )

    # Check blocklist
    block = _check_blocked(parsed, inbox)
    if block:
        details.append(f"Blocked: {block}")
        passed = True
        if tc.expect:
            if tc.expect.blocked:
                details.append("Expected: blocked")
            else:
                passed = False
                details.append(f"Expected: {tc.expect.workflow} / {tc.expect.action} (not blocked)")
        return TestResult(name=tc.name, passed=passed, details=details)

    # Classify
    wf_name, method, action_type = _classify_and_match(parsed, inbox, config, classify_provider)
    details.append(f"Classified: {wf_name} ({method}) \u2192 {action_type}")

    passed = True
    if tc.expect:
        if tc.expect.blocked:
            passed = False
            details.append("Expected: blocked (but email was not blocked)")
        else:
            expected_parts = []
            if tc.expect.workflow:
                expected_parts.append(tc.expect.workflow)
            if tc.expect.action:
                expected_parts.append(tc.expect.action)
            details.append(f"Expected: {' / '.join(expected_parts)}")

            if tc.expect.workflow and tc.expect.workflow != wf_name:
                passed = False
                details.append(
                    f"\u26a0 MISMATCH: classifier returned \"{wf_name}\", expected \"{tc.expect.workflow}\""
                )
            if tc.expect.action and tc.expect.action != action_type:
                passed = False
                details.append(
                    f"\u26a0 MISMATCH: action is \"{action_type}\", expected \"{tc.expect.action}\""
                )

    return TestResult(name=tc.name, passed=passed, details=details)


def _classify_single(
    parsed: ParsedEmail,
    tc: TestCase,
    inbox: InboxConfig,
    config: Config,
    classify_provider: BaseProvider,
    verbose: bool,
) -> TestResult:
    """Classify a single email and check against expect (for batch sub-results)."""
    wf_name, method, action_type = _classify_and_match(parsed, inbox, config, classify_provider)
    detail = f'"{parsed.subject}" from {parsed.from_addr} \u2192 {wf_name}'

    passed = True
    if tc.expect:
        if tc.expect.workflow and tc.expect.workflow != wf_name:
            passed = False
        if tc.expect.action and tc.expect.action != action_type:
            passed = False

    return TestResult(name=parsed.subject, passed=passed, details=[detail])


# ── Quick command ────────────────────────────────────────────────


def run_quick(
    config_path: str,
    inbox_address: str | None = None,
    from_addr: str | None = None,
    subject: str | None = None,
    body: str | None = None,
    describe: str | None = None,
    live: bool = False,
    verbose: bool = False,
) -> int:
    load_result = load_config(config_path)
    config = load_result.config

    if inbox_address:
        inbox = _find_inbox(config, inbox_address)
    else:
        inbox = config.inboxes[0]

    classify_provider = build_provider(config, inbox.classify_provider)

    if describe:
        gen_provider = build_provider(config, inbox.classify_provider)
        gen = generate_email(gen_provider, describe, from_override=from_addr)
        from_addr = gen.from_addr
        subject = gen.subject
        body = gen.body

    if not from_addr or not subject:
        print("Error: --from and --subject are required (or use --describe)")
        return 1

    body = body or ""

    import sys
    out = sys.stdout

    parsed = _build_parsed_email(
        from_addr=from_addr,
        subject=subject,
        body=body,
        to_addr=inbox.address,
    )

    mode = "live" if live else "dry-run"
    out.write(f"\nmailagent test quick — {mode}, inbox: {inbox.address}\n\n")
    out.write(f"From: {from_addr}\n")
    out.write(f"Subject: {subject}\n")
    if verbose:
        out.write(f"Body: {body[:500]}\n")
    out.write("\n")

    block = _check_blocked(parsed, inbox)
    if block:
        out.write(f"Blocklist: matched ({block})\n")
        out.write("Action: blocked\n\nDone.\n")
        return 0

    out.write("Blocklist: not matched\n")

    wf_name, method, action_type = _classify_and_match(parsed, inbox, config, classify_provider)
    out.write(f"Classified: {wf_name} ({method})\n")
    out.write(f"Action: {action_type}\n")

    if live:
        return _run_live_quick(parsed, inbox, config, wf_name)

    out.write("\nDone.\n")
    return 0


def _run_live_quick(
    parsed: ParsedEmail,
    inbox: InboxConfig,
    config: Config,
    workflow_name: str,
) -> int:
    """Send the email through Inbucket and run the full pipeline."""
    # Live quick is a simplified version — just inject and verify delivery
    from . import inbucket as ib

    container = None
    try:
        container, ports = ib.start_inbucket()
        _inject_email_smtp(parsed, "127.0.0.1", ports["smtp"])
        mailbox = parsed.from_addr.split("@")[0] if "@" in parsed.from_addr else parsed.from_addr
        print(f"\nInjected email via SMTP. Check Inbucket UI at http://127.0.0.1:{ports['web']}")
        print("Done.\n")
        return 0
    finally:
        if container:
            ib.stop_inbucket(container)


# ── Live runner ──────────────────────────────────────────────────


def run_live(
    test_config: TestConfig,
    config_path: str,
    filter_name: str | None = None,
    keep: bool = False,
    inbucket_url: str | None = None,
    timeout_seconds: int = 30,
    verbose: bool = False,
) -> int:
    from . import inbucket as ib

    load_result = load_config(config_path)
    config = load_result.config
    inbox = _find_inbox(config, test_config.inbox)

    # Start webhook capture server
    webhook_server = WebhookCaptureServer()
    webhook_server.start()

    container = None
    base_url = inbucket_url or "http://127.0.0.1:9000"

    try:
        if not inbucket_url:
            container, ports = ib.start_inbucket()
            base_url = f"http://127.0.0.1:{ports['web']}"

        smtp_host = "127.0.0.1"
        smtp_port = 2500

        gen_provider: BaseProvider | None = None
        needs_gen = any(tc.generate or tc.generate_batch for tc in test_config.tests)
        if needs_gen:
            gen_provider = _build_generator_provider(test_config.generator, config)

        classify_provider = build_provider(config, inbox.classify_provider)
        reply_provider = build_provider(config, inbox.reply_provider)

        results: list[TestResult] = []

        for tc in test_config.tests:
            if filter_name and filter_name.lower() not in tc.name.lower():
                continue

            result = _run_live_case(
                tc, inbox, config, classify_provider, reply_provider,
                gen_provider, webhook_server, smtp_host, smtp_port,
                base_url, timeout_seconds, verbose,
            )
            results.append(result)

        extra_footer = f"Inbucket UI: {base_url}" if not inbucket_url or keep else None
        print_report("live", f"{inbox.address} (via Inbucket)", results, extra_footer)
        return 0 if all(r.passed for r in results) else 1

    finally:
        webhook_server.stop()
        if container and not keep:
            ib.stop_inbucket(container)
        elif container and keep:
            print(f"Inbucket left running at {base_url}")


def _run_live_case(
    tc: TestCase,
    inbox: InboxConfig,
    config: Config,
    classify_provider: BaseProvider,
    reply_provider: BaseProvider,
    gen_provider: BaseProvider | None,
    webhook_server: WebhookCaptureServer,
    smtp_host: str,
    smtp_port: int,
    inbucket_url: str,
    timeout_seconds: int,
    verbose: bool,
) -> TestResult:
    from . import inbucket as ib
    from ..core.workflows import execute

    details: list[str] = []

    # Generate or construct email
    if tc.generate:
        if gen_provider is None:
            return TestResult(name=tc.name, passed=False, details=["No generator provider"])
        try:
            gen = generate_email(
                gen_provider,
                tc.generate["description"],
                from_override=tc.generate.get("from"),
            )
        except Exception as exc:
            return TestResult(name=tc.name, passed=False, details=[f"Generation failed: {exc}"])
        email_data = gen
        details.append(f'Generated: "{gen.subject}" from {gen.from_addr}')

    elif tc.email:
        email_data = GeneratedEmail(
            from_addr=tc.email["from"],
            subject=tc.email["subject"],
            body=tc.email.get("body", ""),
        )
        details.append(f'Email: "{tc.email["subject"]}" from {tc.email["from"]}')

    elif tc.generate_batch:
        # For live mode, run batch as individual emails
        if gen_provider is None:
            return TestResult(name=tc.name, passed=False, details=["No generator provider"])
        try:
            batch = generate_batch(
                gen_provider,
                tc.generate_batch["description"],
                tc.generate_batch.get("count", 5),
            )
        except Exception as exc:
            return TestResult(name=tc.name, passed=False, details=[f"Batch generation failed: {exc}"])

        sub_results: list[TestResult] = []
        for gen_email in batch:
            sub = _run_live_single(
                gen_email, tc, inbox, config, classify_provider, reply_provider,
                webhook_server, smtp_host, smtp_port, inbucket_url, timeout_seconds, verbose,
            )
            sub_results.append(sub)

        passed_count = sum(1 for s in sub_results if s.passed)
        all_passed = all(s.passed for s in sub_results)
        details.append(f"[{passed_count}/{len(sub_results)} passed]")
        return TestResult(name=tc.name, passed=all_passed, details=details, sub_results=sub_results)

    else:
        return TestResult(name=tc.name, passed=False, details=["No email source defined"])

    return _run_live_single(
        email_data, tc, inbox, config, classify_provider, reply_provider,
        webhook_server, smtp_host, smtp_port, inbucket_url, timeout_seconds, verbose,
    )


def _run_live_single(
    email_data: GeneratedEmail,
    tc: TestCase,
    inbox: InboxConfig,
    config: Config,
    classify_provider: BaseProvider,
    reply_provider: BaseProvider,
    webhook_server: WebhookCaptureServer,
    smtp_host: str,
    smtp_port: int,
    inbucket_url: str,
    timeout_seconds: int,
    verbose: bool,
) -> TestResult:
    from . import inbucket as ib

    details: list[str] = []
    headers = tc.email.get("headers") if tc.email else None

    parsed = _build_parsed_email(
        from_addr=email_data.from_addr,
        subject=email_data.subject,
        body=email_data.body,
        to_addr=inbox.address,
        headers=headers,
    )

    # Inject via SMTP
    t0 = time.time()
    try:
        _inject_email_smtp(parsed, smtp_host, smtp_port)
    except Exception as exc:
        return TestResult(
            name=tc.name, passed=False,
            details=[f"SMTP injection failed: {exc}"],
        )

    # Verify delivery in Inbucket
    to_local = inbox.address.split("@")[0]
    messages = ib.wait_for_messages(to_local, 1, inbucket_url, timeout=timeout_seconds)
    if messages:
        elapsed = time.time() - t0
        details.append(f"Delivered: \u2713 (Inbucket received in {elapsed:.1f}s)")
    else:
        details.append("Delivered: \u2717 (not received)")
        return TestResult(name=tc.name, passed=False, details=details)

    # Check blocklist
    block = _check_blocked(parsed, inbox)
    if block:
        details.append(f"Blocked: \u2713 ({block})")
        # Verify no reply sent
        sender_local = email_data.from_addr.split("@")[0] if "@" in email_data.from_addr else email_data.from_addr
        time.sleep(2)  # brief wait to confirm no reply
        reply_msgs = ib.get_messages(sender_local, inbucket_url)
        if not reply_msgs:
            details.append("No reply sent: \u2713")
        passed = True
        if tc.expect and not tc.expect.blocked:
            passed = False
            details.append("Expected: not blocked")
        elif tc.expect and tc.expect.blocked:
            details.append("Expected: blocked")
        return TestResult(name=tc.name, passed=passed, details=details)

    # Classify
    wf_name, method, action_type = _classify_and_match(parsed, inbox, config, classify_provider)
    details.append(f"Classified: {wf_name} ({method}) \u2192 {action_type}")

    # Execute workflow (with patched config for live)
    webhook_server.clear()
    patched_config = _patch_config_for_live(config, smtp_host, webhook_server.url)

    from ..core.workflows import execute
    exec_result = execute(
        workflow_name=wf_name,
        parsed_email=parsed,
        inbox=inbox,
        config=patched_config,
        reply_provider=reply_provider,
        dry_run=False,
    )

    # Verify based on action type
    if action_type == "reply":
        sender_local = email_data.from_addr.split("@")[0] if "@" in email_data.from_addr else email_data.from_addr
        reply_msgs = ib.wait_for_messages(sender_local, 1, inbucket_url, timeout=timeout_seconds)
        if reply_msgs:
            details.append("Reply sent: \u2713")
            source = ib.get_message_source(sender_local, reply_msgs[-1]["id"], inbucket_url)
            has_threading = "In-Reply-To:" in source and "References:" in source
            details.append(f"Reply threading: {'\u2713' if has_threading else '\u2717'}")
        else:
            details.append("Reply sent: \u2717")

    elif action_type in ("webhook", "notify"):
        time.sleep(1)  # allow webhook delivery
        if webhook_server.captured:
            details.append(f"Webhook called: \u2713 POST to {webhook_server.url}")
        else:
            details.append("Webhook called: \u2717")

    elif action_type == "ignore":
        sender_local = email_data.from_addr.split("@")[0] if "@" in email_data.from_addr else email_data.from_addr
        time.sleep(2)
        reply_msgs = ib.get_messages(sender_local, inbucket_url)
        if not reply_msgs:
            details.append("No reply sent: \u2713")
        else:
            details.append("No reply sent: \u2717 (unexpected reply found)")

    # Check expectations
    passed = True
    if tc.expect:
        if tc.expect.blocked:
            passed = False
            details.append("Expected: blocked (but was not)")
        else:
            expected_parts = []
            if tc.expect.workflow:
                expected_parts.append(tc.expect.workflow)
            if tc.expect.action:
                expected_parts.append(tc.expect.action)
            if expected_parts:
                details.append(f"Expected: {' / '.join(expected_parts)}")

            if tc.expect.workflow and tc.expect.workflow != wf_name:
                passed = False
                details.append(f"\u26a0 MISMATCH: workflow \"{wf_name}\", expected \"{tc.expect.workflow}\"")
            if tc.expect.action and tc.expect.action != action_type:
                passed = False
                details.append(f"\u26a0 MISMATCH: action \"{action_type}\", expected \"{tc.expect.action}\"")

    # Clean up Inbucket mailbox for next test
    try:
        ib.purge_mailbox(to_local, inbucket_url)
    except Exception:
        pass

    return TestResult(name=tc.name, passed=passed, details=details)


def _inject_email_smtp(parsed: ParsedEmail, host: str, port: int) -> None:
    """Send a ParsedEmail to the given SMTP server (no auth, no TLS)."""
    with smtplib.SMTP(host, port) as smtp:
        smtp.send_message(parsed.raw_msg)


def _patch_config_for_live(config: Config, smtp_host: str, webhook_url: str) -> Config:
    """Return a shallow copy of config with mail_host pointed at Inbucket."""
    from dataclasses import replace

    patched_settings = replace(config.settings, mail_host=smtp_host)
    return replace(config, settings=patched_settings)
