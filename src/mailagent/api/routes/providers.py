from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ...config import ConfigError, ConfigManager, ProviderConfig
from ..models import ProviderRequest, ProviderResponse

router = APIRouter()


def _get_cm(request: Request) -> ConfigManager:
    return request.app.state.config_manager


def _provider_to_response(name: str, p: ProviderConfig) -> ProviderResponse:
    return ProviderResponse(
        name=name,
        type=p.type,
        model=p.model,
        base_url=p.base_url,
        timeout=p.timeout,
        retries=p.retries,
    )


@router.get("", response_model=list[ProviderResponse])
async def list_providers(request: Request) -> list[ProviderResponse]:
    cm = _get_cm(request)
    return [
        _provider_to_response(name, p)
        for name, p in cm.config.providers.items()
    ]


@router.get("/{name}", response_model=ProviderResponse)
async def get_provider(request: Request, name: str) -> ProviderResponse:
    cm = _get_cm(request)
    p = cm.get_provider(name)
    if p is None:
        raise HTTPException(status_code=404, detail=f"Provider not found: {name}")
    return _provider_to_response(name, p)


@router.post("/{name}", response_model=ProviderResponse, status_code=201)
async def create_provider(
    request: Request, name: str, body: ProviderRequest
) -> ProviderResponse:
    cm = _get_cm(request)
    provider = ProviderConfig(
        name=name,
        type=body.type,
        model=body.model,
        api_key=body.api_key,
        base_url=body.base_url,
        timeout=body.timeout,
        retries=body.retries,
        http_referer=body.http_referer,
        x_title=body.x_title,
    )
    try:
        cm.add_provider(name, provider)
    except ConfigError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return _provider_to_response(name, provider)


@router.put("/{name}", response_model=ProviderResponse)
async def update_provider(
    request: Request, name: str, body: ProviderRequest
) -> ProviderResponse:
    cm = _get_cm(request)
    provider = ProviderConfig(
        name=name,
        type=body.type,
        model=body.model,
        api_key=body.api_key,
        base_url=body.base_url,
        timeout=body.timeout,
        retries=body.retries,
        http_referer=body.http_referer,
        x_title=body.x_title,
    )
    try:
        cm.update_provider(name, provider)
    except ConfigError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _provider_to_response(name, provider)


@router.delete("/{name}", status_code=204)
async def delete_provider(request: Request, name: str) -> None:
    cm = _get_cm(request)
    try:
        cm.remove_provider(name)
    except ConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
