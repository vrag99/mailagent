from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class ProviderRequest(BaseModel):
    type: str = Field(description="Provider type: openai, anthropic, gemini, openrouter, groq")
    model: str = Field(min_length=1)
    api_key: str = Field(min_length=1)
    base_url: str | None = None
    timeout: int = 30
    retries: int = 1
    http_referer: str | None = None
    x_title: str | None = None


class ProviderResponse(BaseModel):
    name: str
    type: str
    model: str
    base_url: str | None = None
    timeout: int = 30
    retries: int = 1


class KeywordMatchRequest(BaseModel):
    any: list[str] | None = None
    all: list[str] | None = None


class WorkflowMatchRequest(BaseModel):
    intent: str = Field(min_length=1)
    keywords: KeywordMatchRequest | None = None


class WorkflowActionRequest(BaseModel):
    type: str = Field(description="Action type: reply, ignore, notify, webhook")
    prompt: str | None = None
    webhook: str | None = None
    url: str | None = None
    method: str = "POST"
    headers: dict[str, str] | None = None
    payload: dict | None = None
    also_reply: bool = False
    also_webhook: bool = False
    webhook_url: str | None = None


class WorkflowRequest(BaseModel):
    name: str = Field(min_length=1)
    match: WorkflowMatchRequest
    action: WorkflowActionRequest


class WorkflowResponse(BaseModel):
    name: str
    match: WorkflowMatchRequest
    action: WorkflowActionRequest


class BlocklistRequest(BaseModel):
    from_patterns: list[str] = Field(default_factory=list)
    headers: list[str] = Field(default_factory=list)


class InboxRequest(BaseModel):
    address: str = Field(description="Email address for the inbox")
    password: str = Field(min_length=1, description="Mailbox password")
    name: str | None = None
    classify_provider: str | None = None
    reply_provider: str | None = None
    system_prompt: str | None = None
    blocklist: BlocklistRequest | None = None
    workflows: list[WorkflowRequest] = Field(min_length=1)


class InboxUpdateRequest(BaseModel):
    name: str | None = None
    classify_provider: str | None = None
    reply_provider: str | None = None
    system_prompt: str | None = None
    blocklist: BlocklistRequest | None = None


class InboxResponse(BaseModel):
    address: str
    name: str | None = None
    classify_provider: str
    reply_provider: str
    system_prompt: str | None = None
    workflows: list[WorkflowResponse] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    detail: str
