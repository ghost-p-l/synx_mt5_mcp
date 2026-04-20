"""SYNX_EA File IPC Bridge — communicates with SYNX_EA via JSON file exchange.

SYNX_EA v1.10 architecture:
  - Writes state snapshots to  MQL5\\Files\\synx\\state\\*.json  every 500 ms
  - Reads commands from        MQL5\\Files\\synx\\cmd\\*.json
  - Writes responses to        MQL5\\Files\\synx\\resp\\{req_id}.json
"""

import asyncio
import contextlib
import json
import time
import uuid
from pathlib import Path
from typing import Any

import structlog

log = structlog.get_logger(__name__)


class SYNXEABridge:
    """
    File-based IPC bridge for SYNX_EA v1.10.

    State files (read-only, refreshed by EA every 500 ms):
        health.json, account.json, terminal.json,
        positions.json, charts.json, symbols.json

    Command files (written here, deleted by EA after processing):
        cmd/{req_id}.json  →  {"cmd": "...", "req_id": "...", ...}

    Response files (written by EA, deleted here after reading):
        resp/{req_id}.json  →  {"req_id": "...", "cmd": "...", "data": {...}}
    """

    POLL_INTERVAL = 0.1     # seconds between response polls
    COMMAND_TIMEOUT = 10.0  # seconds to wait for EA response

    def __init__(self, files_dir: Path):
        self.files_dir = files_dir
        self.state_dir = files_dir  # Flat: synx__state*.json
        self.cmd_dir = files_dir     # Flat: cmd_*.json
        self.resp_dir = files_dir    # Flat: resp_*.json

    def is_available(self) -> bool:
        """Return True if the EA state directory exists and has data."""
        return (self.state_dir / "health.json").exists()

    def _read_state(self, filename: str) -> dict[str, Any]:
        """Read a JSON state snapshot; returns {} on missing/parse error."""
        path = self.state_dir / filename
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            log.warning("ea_file_ipc_read_error", file=filename, error=str(exc))
            return {}

    async def _send_command(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Write a command file and poll until the EA posts a response."""
        req_id = uuid.uuid4().hex
        payload["req_id"] = req_id

        cmd_path = self.cmd_dir / f"cmd_{req_id}.json"
        try:
            cmd_path.write_text(json.dumps(payload), encoding="utf-8")
        except Exception as exc:
            return {"error": f"Failed to write command: {exc}", "code": 500}

        resp_path = self.resp_dir / f"resp_{req_id}.json"
        deadline = time.monotonic() + self.COMMAND_TIMEOUT

        while time.monotonic() < deadline:
            if resp_path.exists():
                try:
                    raw = json.loads(resp_path.read_text(encoding="utf-8"))
                    resp_path.unlink(missing_ok=True)
                    # EA wraps result under "data" key
                    return raw.get("data", raw)
                except Exception as exc:
                    resp_path.unlink(missing_ok=True)
                    return {"error": str(exc), "code": 500}
            await asyncio.sleep(self.POLL_INTERVAL)

        # Timed out — clean up stale command
        with contextlib.suppress(Exception):
            cmd_path.unlink(missing_ok=True)
        return {"error": "Timeout waiting for EA response", "code": 408}

    def _resolve_chart_id(self, approx_id: int) -> int | None:
        """
        Resolve an approximate chart ID to the real MT5 chart ID.

        Chart IDs exceed JavaScript's Number.MAX_SAFE_INTEGER (2^53), so they
        lose precision when serialised through the Node.js MCP client.  We
        find the state-file chart whose ID is numerically closest to the
        received value (tolerance = 100 units covers all known JS precision
        drift for these magnitudes).
        """
        charts = self._read_state("charts.json").get("charts", [])
        if not charts:
            return None
        for c in charts:
            if c["id"] == approx_id:
                return approx_id
        best = min(charts, key=lambda c: abs(c["id"] - approx_id))
        if abs(best["id"] - approx_id) < 100:
            return best["id"]
        return None

    # ------------------------------------------------------------------
    # State reads — no round-trip needed, just read the snapshot file
    # ------------------------------------------------------------------

    async def ea_chart_list(self) -> list[dict[str, Any]]:
        """List all open charts from the last state snapshot."""
        return self._read_state("charts.json").get("charts", [])

    async def ea_health(self) -> dict[str, Any]:
        """Read EA health snapshot."""
        return self._read_state("health.json")

    async def ea_account(self) -> dict[str, Any]:
        """Read account snapshot from EA state."""
        return self._read_state("account.json")

    async def ea_terminal(self) -> dict[str, Any]:
        """Read terminal snapshot from EA state."""
        return self._read_state("terminal.json")

    async def ea_positions(self) -> list[dict[str, Any]]:
        """Read positions snapshot from EA state."""
        return self._read_state("positions.json").get("positions", [])

    async def ea_symbols(self) -> list[dict[str, Any]]:
        """Read symbols snapshot from EA state (refreshed every 60 s)."""
        return self._read_state("symbols.json").get("symbols", [])

    # ------------------------------------------------------------------
    # Commands — write to cmd/, poll resp/ for reply
    # ------------------------------------------------------------------

    async def ea_chart_screenshot(
        self,
        chart_id: int,
        width: int = 1280,
        height: int = 720,
        align_to_right: bool = True,
    ) -> dict[str, Any]:
        """Capture a chart screenshot. Returns {image_base64, filename} on success."""
        import base64

        real_id = self._resolve_chart_id(chart_id)
        if real_id is None:
            return {"error": f"Chart {chart_id} not found", "code": 404}

        resp = await self._send_command({
            "cmd": "screenshot",
            "chart_id": real_id,
        })

        if "error" in resp:
            return resp

        filename = resp.get("filename", "")
        if not filename:
            return {"error": "EA returned no filename", "code": 500}

        # The EA saves the PNG to MQL5\Files\ (our files_dir root)
        png_path = self.files_dir / filename
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if png_path.exists():
                break
            await asyncio.sleep(0.1)

        if not png_path.exists():
            return {"error": f"Screenshot file not found: {png_path}", "code": 404}

        try:
            image_b64 = base64.b64encode(png_path.read_bytes()).decode("utf-8")
            png_path.unlink(missing_ok=True)
            return {"image_base64": image_b64, "filename": filename, "status": "ok"}
        except Exception as exc:
            return {"error": f"Failed to read screenshot: {exc}", "code": 500}

    async def ea_get_rates(
        self,
        symbol: str,
        timeframe: str = "H1",
        count: int = 100,
    ) -> dict[str, Any]:
        """Get OHLCV bars for a symbol via EA. Returns {symbol, timeframe, rates:[]}."""
        return await self._send_command({
            "cmd": "get_rates",
            "symbol": symbol,
            "timeframe": timeframe,
            "count": count,
        })

    # ------------------------------------------------------------------
    # Stubs for chart operations not yet in SYNX_EA v1.10
    # ------------------------------------------------------------------

    async def ea_chart_open(self, symbol: str, timeframe: str) -> dict[str, Any]:
        return {"error": "chart_open not implemented in SYNX_EA v1.10", "code": 501}

    async def ea_chart_close(self, chart_id: int) -> dict[str, Any]:
        return {"error": "chart_close not implemented in SYNX_EA v1.10", "code": 501}

    async def ea_chart_set_symbol_timeframe(
        self, chart_id: int, symbol: str | None, timeframe: str | None
    ) -> None:
        return None

    async def ea_chart_apply_template(
        self, chart_id: int, template_name: str
    ) -> dict[str, Any]:
        return {"error": "chart_apply_template not implemented in SYNX_EA v1.10", "code": 501}

    async def ea_chart_save_template(
        self, chart_id: int, template_name: str
    ) -> dict[str, Any]:
        return {"error": "chart_save_template not implemented in SYNX_EA v1.10", "code": 501}

    async def ea_chart_navigate(
        self, chart_id: int, position: str, shift: int
    ) -> dict[str, Any]:
        return {"error": "chart_navigate not implemented in SYNX_EA v1.10", "code": 501}

    async def ea_chart_indicator_add(
        self,
        chart_id: int,
        indicator_path: str,
        window: int,
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        return {"error": "chart_indicator_add not implemented in SYNX_EA v1.10", "code": 501}

    async def ea_chart_indicator_list(
        self, chart_id: int, window: int | None = None
    ) -> list[dict[str, Any]]:
        return []

    async def ea_run_script(
        self,
        chart_id: int,
        script_name: str,
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        return {"error": "run_script not implemented in SYNX_EA v1.10", "code": 501}
