"""Human-in-the-Loop Gate - Approval queue for sensitive operations."""

import asyncio
import hashlib
import hmac
import json
import secrets
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
import structlog

from synx_mt5.audit import AuditEngine, AuditEventType
from synx_mt5.risk.preflight import OrderRequest

log = structlog.get_logger(__name__)


class HITLGate:
    """Human-in-the-Loop approval gate for sensitive operations."""

    def __init__(self, config: dict, audit: AuditEngine, storage_path: Path | None = None):
        self.enabled = config.get("enabled", True)
        self.timeout_secs = config.get("timeout_seconds", 300)
        self.sink = config.get("sink", "terminal")
        self.webhook_url = config.get("webhook_url")
        self.webhook_secret = config.get("webhook_secret")
        self.telegram_bot_token = config.get("telegram_bot_token")
        self.telegram_chat_id = config.get("telegram_chat_id")
        self._pending: dict[str, OrderRequest | None] = {}
        self._audit = audit
        self._state_file = (storage_path or Path("~/.synx-mt5")).expanduser() / "hitl_pending.json"
        self._http_client: httpx.AsyncClient | None = None
        self._load_pending()

    def _load_pending(self) -> None:
        """Load pending approvals from state file."""
        if self._state_file.exists():
            try:
                data = json.loads(self._state_file.read_text())
                for approval_id in data.get("pending", []):
                    if approval_id not in self._pending:
                        self._pending[approval_id] = None
            except Exception:
                pass

    def _save_pending(self) -> None:
        """Save pending approval IDs to state file."""
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._state_file.write_text(json.dumps({"pending": list(self._pending.keys())}))

    def _add_pending(self, approval_id: str, req: OrderRequest) -> None:
        """Add approval to pending and persist."""
        self._pending[approval_id] = req
        self._save_pending()

    def _remove_pending(self, approval_id: str) -> None:
        """Remove approval from pending and persist."""
        self._pending.pop(approval_id, None)
        self._save_pending()

    async def request_approval(self, req: OrderRequest) -> str:
        """Request human approval for an order."""
        if not self.enabled:
            return "auto_approved"

        approval_id = secrets.token_hex(8)
        self._add_pending(approval_id, req)

        await self._emit(self._format_message(approval_id, req))

        self._audit.log(
            AuditEventType.RISK_HITL_REQUIRED,
            {
                "approval_id": approval_id,
                "symbol": req.symbol,
                "volume": req.volume,
                "order_type": req.order_type,
            },
        )

        deadline = time.time() + self.timeout_secs
        while time.time() < deadline:
            await asyncio.sleep(1)
            if approval_id not in self._pending:
                return approval_id

        self._remove_pending(approval_id)
        raise TimeoutError(f"HITL approval timed out after {self.timeout_secs}s")

    def approve(self, approval_id: str, approver: str = "human") -> bool:
        """Approve a pending request."""
        if approval_id in self._pending:
            self._remove_pending(approval_id)
            self._audit.log(
                AuditEventType.RISK_HITL_APPROVED,
                {
                    "approval_id": approval_id,
                    "approver": approver,
                },
            )
            log.info("hitl_approved", approval_id=approval_id, approver=approver)
            return True
        return False

    def reject(self, approval_id: str, approver: str = "human") -> bool:
        """Reject a pending request."""
        if approval_id in self._pending:
            self._remove_pending(approval_id)
            self._audit.log(
                AuditEventType.RISK_HITL_REJECTED,
                {
                    "approval_id": approval_id,
                    "approver": approver,
                },
            )
            log.warning("hitl_rejected", approval_id=approval_id, approver=approver)
            return True
        return False

    def get_pending(self) -> dict:
        """Get all pending approvals."""
        return {
            "count": len(self._pending),
            "pending": list(self._pending.keys()),
        }

    async def ask_approval(self, operation: str, params: dict) -> str:
        """
        Request human approval for a generic operation.

        Args:
            operation: Operation name (e.g. "backtest_run", "backtest_optimize")
            params: Operation parameters
        Returns:
            Approval ID if approved
        Raises:
            TimeoutError: If approval times out
        """
        if not self.enabled:
            return "auto_approved"

        approval_id = secrets.token_hex(8)
        self._pending[approval_id] = None

        message = self._format_generic_message(approval_id, operation, params)
        await self._emit(message)

        self._audit.log(
            AuditEventType.RISK_HITL_REQUIRED,
            {
                "approval_id": approval_id,
                "operation": operation,
                "params": params,
            },
        )

        deadline = time.time() + self.timeout_secs
        while time.time() < deadline:
            await asyncio.sleep(1)
            if approval_id not in self._pending:
                return approval_id

        self._remove_pending(approval_id)
        raise TimeoutError(f"Approval timed out after {self.timeout_secs}s for {operation}")

    def _format_generic_message(self, approval_id: str, operation: str, params: dict) -> str:
        """Format approval message for a generic operation."""
        params_lines = "\n".join(f"  {k}: {v}" for k, v in params.items())
        return (
            f"\n{'=' * 60}\n"
            f"  SYNX-MT5 {operation.upper()} APPROVAL REQUIRED\n"
            f"{'=' * 60}\n"
            f"  ID:      {approval_id}\n"
            f"{params_lines}\n"
            f"{'=' * 60}\n"
            f"  Approve: synx-mt5 risk approve {approval_id}\n"
            f"  Reject:  synx-mt5 risk reject {approval_id}\n"
            f"{'=' * 60}\n"
        )

    async def _emit(self, message: str):
        """Emit approval request to configured sink."""
        if self.sink == "terminal":
            print(message)
        elif self.sink == "webhook":
            await self._emit_webhook(message)
        elif self.sink == "telegram":
            await self._emit_telegram(message)

    async def _emit_webhook(self, message: str) -> None:
        """Send approval request via webhook POST with optional HMAC-SHA256 signing."""
        if not self.webhook_url:
            log.warning("hitl_webhook_no_url_configured")
            return

        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0)

        payload = {
            "event": "hitl_approval_required",
            "message": message,
            "sink": "webhook",
            "timestamp": datetime.now(UTC).isoformat(),
        }

        headers = {"Content-Type": "application/json"}

        if self.webhook_secret:
            body = json.dumps(payload, separators=(",", ":"))
            signature = hmac.new(
                self.webhook_secret.encode("utf-8"),
                body.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            headers["X-SYNX-Signature"] = f"sha256={signature}"
        else:
            body = json.dumps(payload)

        try:
            response = await self._http_client.post(
                self.webhook_url,
                content=body.encode("utf-8"),
                headers=headers,
            )
            response.raise_for_status()
            log.info("hitl_webhook_sent", url=self.webhook_url, status=response.status_code)
        except httpx.TimeoutException:
            log.error("hitl_webhook_timeout", url=self.webhook_url)
        except httpx.HTTPStatusError as e:
            log.error(
                "hitl_webhook_http_error", url=self.webhook_url, status=e.response.status_code
            )
        except Exception as e:
            log.error("hitl_webhook_error", url=self.webhook_url, error=str(e))

    async def _emit_telegram(self, message: str) -> None:
        """Send approval request via Telegram Bot API."""
        if not self.telegram_bot_token:
            log.warning("hitl_telegram_no_token_configured")
            return

        if not self.telegram_chat_id:
            log.warning("hitl_telegram_no_chat_id_configured")
            return

        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0)

        api_url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"

        formatted = self._format_telegram_message(message)

        payload = {
            "chat_id": self.telegram_chat_id,
            "text": formatted,
            "parse_mode": "HTML",
            "reply_markup": {
                "inline_keyboard": [
                    [
                        {"text": "✅ Approve", "callback_data": "hitl_approve"},
                        {"text": "❌ Reject", "callback_data": "hitl_reject"},
                    ]
                ]
            },
        }

        try:
            response = await self._http_client.post(api_url, json=payload)
            response.raise_for_status()
            log.info(
                "hitl_telegram_sent",
                bot_token=self.telegram_bot_token[:8] + "...",
                chat_id=self.telegram_chat_id,
            )
        except httpx.TimeoutException:
            log.error("hitl_telegram_timeout")
        except httpx.HTTPStatusError as e:
            log.error("hitl_telegram_http_error", status=e.response.status_code)
        except Exception as e:
            log.error("hitl_telegram_error", error=str(e))

    def _format_telegram_message(self, terminal_message: str) -> str:
        """Format terminal message for Telegram HTML rendering."""
        lines = terminal_message.strip().split("\n")
        html_lines = []

        for line in lines:
            if "=" in line:
                parts = line.split("=", 1)
                label = parts[0].strip()
                value = parts[1].strip() if len(parts) > 1 else ""
                html_lines.append(f"<b>{label}</b>: {value}")
            else:
                html_lines.append(line)

        return "\n".join(html_lines)

    def _format_message(self, approval_id: str, req: OrderRequest) -> str:
        """Format approval request message."""
        return (
            f"\n{'=' * 60}\n"
            f"  SYNX-MT5 ORDER APPROVAL REQUIRED\n"
            f"{'=' * 60}\n"
            f"  ID:      {approval_id}\n"
            f"  Symbol:  {req.symbol}\n"
            f"  Action:  {req.order_type}\n"
            f"  Volume:  {req.volume} lots\n"
            f"  Price:   {req.price}\n"
            f"  SL:      {req.sl or 'None'}\n"
            f"  TP:      {req.tp or 'None'}\n"
            f"{'=' * 60}\n"
            f"  Approve: synx-mt5 risk approve {approval_id}\n"
            f"  Reject:  synx-mt5 risk reject {approval_id}\n"
            f"{'=' * 60}\n"
        )
