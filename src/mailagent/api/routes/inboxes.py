from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ...config import (
    Blocklist,
    ConfigError,
    ConfigManager,
    InboxConfig,
    KeywordMatch,
    Workflow,
    WorkflowAction,
    WorkflowMatch,
)
from ...provisioner import Provisioner
from ..models import (
    InboxRequest,
    InboxResponse,
    InboxUpdateRequest,
    KeywordMatchRequest,
    WorkflowActionRequest,
    WorkflowMatchRequest,
    WorkflowResponse,
)

router = APIRouter()


def _get_cm(request: Request) -> ConfigManager:
    return request.app.state.config_manager


def _get_provisioner(request: Request) -> Provisioner | None:
    return getattr(request.app.state, "provisioner", None)


def _inbox_to_response(inbox: InboxConfig) -> InboxResponse:
    workflows = []
    for w in inbox.workflows:
        kw = None
        if w.match.keywords:
            kw = KeywordMatchRequest(any=w.match.keywords.any, all=w.match.keywords.all)
        workflows.append(
            WorkflowResponse(
                name=w.name,
                match=WorkflowMatchRequest(intent=w.match.intent, keywords=kw),
                action=WorkflowActionRequest(
                    type=w.action.type,
                    prompt=w.action.prompt,
                    webhook=w.action.webhook,
                    url=w.action.url,
                    method=w.action.method,
                    headers=w.action.headers,
                    payload=w.action.payload,
                    also_reply=w.action.also_reply,
                    also_webhook=w.action.also_webhook,
                    webhook_url=w.action.webhook_url,
                ),
            )
        )
    return InboxResponse(
        address=inbox.address,
        name=inbox.name,
        classify_provider=inbox.classify_provider,
        reply_provider=inbox.reply_provider,
        system_prompt=inbox.system_prompt,
        workflows=workflows,
    )


def _workflow_request_to_model(wr: WorkflowResponse | object) -> Workflow:
    keywords = None
    if wr.match.keywords:
        keywords = KeywordMatch(any=wr.match.keywords.any, all=wr.match.keywords.all)
    return Workflow(
        name=wr.name,
        match=WorkflowMatch(intent=wr.match.intent, keywords=keywords),
        action=WorkflowAction(
            type=wr.action.type,
            prompt=wr.action.prompt,
            webhook=wr.action.webhook,
            url=wr.action.url,
            method=wr.action.method,
            headers=wr.action.headers,
            payload=wr.action.payload,
            also_reply=wr.action.also_reply,
            also_webhook=wr.action.also_webhook,
            webhook_url=wr.action.webhook_url,
        ),
    )


@router.get("", response_model=list[InboxResponse])
async def list_inboxes(request: Request) -> list[InboxResponse]:
    cm = _get_cm(request)
    return [_inbox_to_response(inbox) for inbox in cm.config.inboxes]


@router.get("/{address}", response_model=InboxResponse)
async def get_inbox(request: Request, address: str) -> InboxResponse:
    cm = _get_cm(request)
    inbox = cm.get_inbox(address)
    if inbox is None:
        raise HTTPException(status_code=404, detail=f"Inbox not found: {address}")
    return _inbox_to_response(inbox)


@router.post("", response_model=InboxResponse, status_code=201)
async def create_inbox(request: Request, body: InboxRequest) -> InboxResponse:
    cm = _get_cm(request)
    config = cm.config

    classify = body.classify_provider or config.defaults.classify_provider
    reply = body.reply_provider or config.defaults.reply_provider

    if classify not in config.providers:
        raise HTTPException(status_code=400, detail=f"Unknown classify_provider: {classify}")
    if reply not in config.providers:
        raise HTTPException(status_code=400, detail=f"Unknown reply_provider: {reply}")

    blocklist = None
    if body.blocklist:
        blocklist = Blocklist(
            from_patterns=body.blocklist.from_patterns,
            headers=body.blocklist.headers,
        )

    workflows = [_workflow_request_to_model(wr) for wr in body.workflows]

    inbox = InboxConfig(
        address=body.address.lower(),
        credentials={"password": body.password},
        workflows=workflows,
        classify_provider=classify,
        reply_provider=reply,
        name=body.name,
        system_prompt=body.system_prompt,
        blocklist=blocklist,
    )

    provisioner = _get_provisioner(request)
    if provisioner:
        try:
            provisioner.add_account(body.address, body.password)
        except Exception as exc:
            raise HTTPException(
                status_code=500, detail=f"Failed to provision mailbox: {exc}"
            )

    try:
        cm.add_inbox(inbox)
    except ConfigError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    return _inbox_to_response(inbox)


@router.patch("/{address}", response_model=InboxResponse)
async def update_inbox(
    request: Request, address: str, body: InboxUpdateRequest
) -> InboxResponse:
    cm = _get_cm(request)
    inbox = cm.get_inbox(address)
    if inbox is None:
        raise HTTPException(status_code=404, detail=f"Inbox not found: {address}")

    config = cm.config

    if body.name is not None:
        inbox.name = body.name
    if body.classify_provider is not None:
        if body.classify_provider not in config.providers:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown classify_provider: {body.classify_provider}",
            )
        inbox.classify_provider = body.classify_provider
    if body.reply_provider is not None:
        if body.reply_provider not in config.providers:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown reply_provider: {body.reply_provider}",
            )
        inbox.reply_provider = body.reply_provider
    if body.system_prompt is not None:
        inbox.system_prompt = body.system_prompt
    if body.blocklist is not None:
        inbox.blocklist = Blocklist(
            from_patterns=body.blocklist.from_patterns,
            headers=body.blocklist.headers,
        )

    try:
        cm.update_inbox(address, inbox)
    except ConfigError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return _inbox_to_response(inbox)


@router.delete("/{address}", status_code=204)
async def delete_inbox(request: Request, address: str) -> None:
    cm = _get_cm(request)

    provisioner = _get_provisioner(request)
    if provisioner:
        try:
            provisioner.remove_account(address)
        except Exception:
            pass  # Best-effort removal from mailserver

    try:
        cm.remove_inbox(address)
    except ConfigError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
