from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ...config import (
    ConfigError,
    ConfigManager,
    KeywordMatch,
    Workflow,
    WorkflowAction,
    WorkflowMatch,
)
from ..models import (
    KeywordMatchRequest,
    WorkflowActionRequest,
    WorkflowMatchRequest,
    WorkflowRequest,
    WorkflowResponse,
)

router = APIRouter()


def _get_cm(request: Request) -> ConfigManager:
    return request.app.state.config_manager


def _workflow_to_response(w: Workflow) -> WorkflowResponse:
    kw = None
    if w.match.keywords:
        kw = KeywordMatchRequest(any=w.match.keywords.any, all=w.match.keywords.all)
    return WorkflowResponse(
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


def _request_to_workflow(wr: WorkflowRequest) -> Workflow:
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


@router.get("", response_model=list[WorkflowResponse])
async def list_workflows(request: Request, inbox_address: str) -> list[WorkflowResponse]:
    cm = _get_cm(request)
    inbox = cm.get_inbox(inbox_address)
    if inbox is None:
        raise HTTPException(status_code=404, detail=f"Inbox not found: {inbox_address}")
    return [_workflow_to_response(w) for w in inbox.workflows]


@router.get("/{workflow_name}", response_model=WorkflowResponse)
async def get_workflow(request: Request, inbox_address: str, workflow_name: str) -> WorkflowResponse:
    cm = _get_cm(request)
    inbox = cm.get_inbox(inbox_address)
    if inbox is None:
        raise HTTPException(status_code=404, detail=f"Inbox not found: {inbox_address}")

    for w in inbox.workflows:
        if w.name == workflow_name:
            return _workflow_to_response(w)
    raise HTTPException(status_code=404, detail=f"Workflow not found: {workflow_name}")


@router.post("", response_model=WorkflowResponse, status_code=201)
async def create_workflow(request: Request, inbox_address: str, body: WorkflowRequest) -> WorkflowResponse:
    cm = _get_cm(request)
    inbox = cm.get_inbox(inbox_address)
    if inbox is None:
        raise HTTPException(status_code=404, detail=f"Inbox not found: {inbox_address}")

    for w in inbox.workflows:
        if w.name == body.name:
            raise HTTPException(status_code=409, detail=f"Workflow already exists: {body.name}")

    workflow = _request_to_workflow(body)
    inbox.workflows.append(workflow)

    try:
        cm.update_inbox(inbox_address, inbox)
    except ConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return _workflow_to_response(workflow)


@router.put("/{workflow_name}", response_model=WorkflowResponse)
async def update_workflow(
    request: Request, inbox_address: str, workflow_name: str, body: WorkflowRequest
) -> WorkflowResponse:
    cm = _get_cm(request)
    inbox = cm.get_inbox(inbox_address)
    if inbox is None:
        raise HTTPException(status_code=404, detail=f"Inbox not found: {inbox_address}")

    found = False
    for i, w in enumerate(inbox.workflows):
        if w.name == workflow_name:
            inbox.workflows[i] = _request_to_workflow(body)
            found = True
            break

    if not found:
        raise HTTPException(status_code=404, detail=f"Workflow not found: {workflow_name}")

    try:
        cm.update_inbox(inbox_address, inbox)
    except ConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return _workflow_to_response(inbox.workflows[i])


@router.delete("/{workflow_name}", status_code=204)
async def delete_workflow(request: Request, inbox_address: str, workflow_name: str) -> None:
    cm = _get_cm(request)
    inbox = cm.get_inbox(inbox_address)
    if inbox is None:
        raise HTTPException(status_code=404, detail=f"Inbox not found: {inbox_address}")

    original_len = len(inbox.workflows)
    inbox.workflows = [w for w in inbox.workflows if w.name != workflow_name]

    if len(inbox.workflows) == original_len:
        raise HTTPException(status_code=404, detail=f"Workflow not found: {workflow_name}")

    if len(inbox.workflows) == 0:
        raise HTTPException(status_code=400, detail="Cannot delete last workflow from inbox")

    try:
        cm.update_inbox(inbox_address, inbox)
    except ConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
