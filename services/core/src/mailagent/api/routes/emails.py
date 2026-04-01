from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

from ...config import ConfigManager
from ...core.mailer import save_to_sent, send_email
from ..models import SendEmailRequest, SendEmailResponse

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_cm(request: Request) -> ConfigManager:
    return request.app.state.config_manager


@router.post("/send", response_model=SendEmailResponse)
async def send(request: Request, body: SendEmailRequest) -> SendEmailResponse:
    cm = _get_cm(request)
    inbox = cm.get_inbox(body.from_inbox)
    if inbox is None:
        raise HTTPException(
            status_code=404, detail=f"Inbox not found: {body.from_inbox}"
        )

    mail_host = cm.config.settings.mail_host
    password = inbox.credentials.get("password", "")
    if not password:
        raise HTTPException(
            status_code=400, detail=f"Inbox {body.from_inbox} has no password configured"
        )

    try:
        msg = send_email(
            mail_host=mail_host,
            inbox_address=inbox.address,
            password=password,
            to=body.to,
            subject=body.subject,
            body=body.body,
            cc=body.cc or None,
            bcc=body.bcc or None,
            content_type=body.content_type,
            inbox_name=inbox.name,
            in_reply_to=body.in_reply_to,
            references=body.references,
        )
    except Exception as exc:
        logger.error("Failed to send email: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to send email: {exc}")

    message_id = msg.get("Message-ID", "")

    try:
        save_to_sent(
            msg=msg,
            mail_host=mail_host,
            inbox_address=inbox.address,
            password=password,
        )
    except Exception as exc:
        logger.warning("Email sent but failed to save to Sent folder: %s", exc)

    return SendEmailResponse(ok=True, message_id=message_id)
