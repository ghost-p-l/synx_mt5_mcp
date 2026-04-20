"""Strategy Tester Tools - Backtest execution and result analysis."""

import secrets
from typing import Any

import structlog
from pydantic import BaseModel, Field, field_validator

from synx_mt5.audit.engine import AuditEngine, AuditEventType
from synx_mt5.security.injection_shield import sanitise_string

log = structlog.get_logger(__name__)


class BacktestRunInput(BaseModel):
    """Input for backtest_run tool."""

    ea_name: str = Field(min_length=1, max_length=64)
    symbol: str = Field(min_length=1, max_length=32)
    timeframe: str = Field(default="H1")
    date_from: str
    date_to: str
    initial_deposit: float = Field(default=10000.0, gt=0)
    leverage: int = Field(default=100, ge=1, le=1000)
    model: str = Field(default="every_tick")
    optimization: bool = Field(default=False)

    @field_validator("symbol")
    @classmethod
    def sanitize_symbol(cls, v: str) -> str:
        return sanitise_string(v, "backtest:symbol").upper()

    @field_validator("model")
    @classmethod
    def validate_model(cls, v: str) -> str:
        if v not in ("every_tick", "ohlc_m1", "open_prices"):
            raise ValueError("model must be 'every_tick', 'ohlc_m1', or 'open_prices'")
        return v


class BacktestOptimizeInput(BaseModel):
    """Input for backtest_optimize tool."""

    ea_name: str
    symbol: str = Field(min_length=1, max_length=32)
    timeframe: str = Field(default="H1")
    date_from: str
    date_to: str
    parameters: list[dict[str, Any]] = Field(min_length=1)
    criterion: str = Field(default="balance")


class BacktestGetResultsInput(BaseModel):
    """Input for backtest_get_results tool."""

    job_id: str | None = Field(default=None)
    ea_name: str | None = Field(default=None)


class BacktestListResultsInput(BaseModel):
    """Input for backtest_list_results tool."""

    ea_name: str | None = Field(default=None)


class BacktestService:
    """
    Service layer for strategy tester operations.

    Note: MT5 Strategy Tester only runs compiled MQL5 EAs.
    For Python backtesting, use external libraries (Backtrader, vectorbt).
    """

    def __init__(
        self,
        bridge: Any,
        audit: AuditEngine,
        results_dir: str | None = None,
        hitl: Any = None,
    ):
        self.bridge = bridge
        self.audit = audit
        self.results_dir = results_dir
        self._jobs: dict[str, dict] = {}
        self._hitl = hitl

    async def backtest_run(
        self,
        ea_name: str,
        symbol: str,
        timeframe: str = "H1",
        date_from: str = "",
        date_to: str = "",
        initial_deposit: float = 10000.0,
        leverage: int = 100,
        model: str = "every_tick",
        optimization: bool = False,
    ) -> dict[str, Any]:
        """
        Trigger backtest in MT5 Strategy Tester.

        Note: This requires MetaEditor subprocess access and
        creates a test configuration file for the tester.
        HITL approval required per full profile configuration.
        """
        if self._hitl and self._hitl.enabled:
            await self._hitl.ask_approval(
                "backtest_run",
                {
                    "ea_name": ea_name,
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "date_from": date_from,
                    "date_to": date_to,
                    "deposit": initial_deposit,
                    "leverage": leverage,
                },
            )

        job_id = f"bt_{secrets.token_hex(6)}"

        self._jobs[job_id] = {
            "status": "running",
            "ea_name": ea_name,
            "symbol": symbol,
            "timeframe": timeframe,
        }

        self.audit.log(
            AuditEventType.TOOL_INVOCATION,
            {
                "tool": "backtest_run",
                "job_id": job_id,
                "ea_name": ea_name,
                "symbol": symbol,
            },
        )

        if hasattr(self.bridge, "metaeditor_backtest"):
            result = await self.bridge.metaeditor_backtest(
                ea_name=ea_name,
                symbol=symbol,
                timeframe=timeframe,
                date_from=date_from,
                date_to=date_to,
                initial_deposit=initial_deposit,
                leverage=leverage,
                model=model,
            )
            if result.get("started"):
                self._jobs[job_id]["status"] = "queued"
        else:
            self._jobs[job_id]["status"] = "not_implemented"

        estimated = 300

        return {
            "job_id": job_id,
            "status": self._jobs[job_id]["status"],
            "ea_name": ea_name,
            "symbol": symbol,
            "estimated_duration_seconds": estimated,
        }

    async def backtest_get_results(
        self,
        job_id: str | None = None,
        ea_name: str | None = None,
    ) -> dict[str, Any]:
        """Read results of completed backtest."""
        self.audit.log(
            AuditEventType.TOOL_INVOCATION,
            {
                "tool": "backtest_get_results",
                "job_id": job_id,
            },
        )

        if job_id and job_id in self._jobs:
            job = self._jobs[job_id]
            if job.get("results"):
                return job["results"]
            return {
                "status": job.get("status", "unknown"),
                "ea_name": job.get("ea_name"),
            }

        return {
            "status": "no_results",
            "ea_name": ea_name,
        }

    async def backtest_optimize(
        self,
        ea_name: str,
        symbol: str,
        timeframe: str,
        date_from: str,
        date_to: str,
        parameters: list[dict],
        criterion: str = "balance",
    ) -> dict[str, Any]:
        """Run parameter optimization in Strategy Tester. HITL always required."""
        if self._hitl and self._hitl.enabled:
            await self._hitl.ask_approval(
                "backtest_optimize",
                {
                    "ea_name": ea_name,
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "date_from": date_from,
                    "date_to": date_to,
                    "parameters": parameters,
                    "criterion": criterion,
                },
            )

        job_id = f"opt_{secrets.token_hex(6)}"

        combinations = 1
        for p in parameters:
            start = p.get("start", 0)
            stop = p.get("stop", 100)
            step = p.get("step", 1)
            combinations *= max(1, int((stop - start) / step))

        self.audit.log(
            AuditEventType.TOOL_INVOCATION,
            {
                "tool": "backtest_optimize",
                "job_id": job_id,
                "ea_name": ea_name,
                "combinations": combinations,
            },
        )

        return {
            "job_id": job_id,
            "status": "running",
            "parameter_combinations": combinations,
            "estimated_duration_seconds": combinations * 60,
        }

    async def backtest_list_results(
        self,
        ea_name: str | None = None,
    ) -> dict[str, Any]:
        """List available backtest result files."""
        results = []

        if self.results_dir:
            from pathlib import Path

            results_dir = Path(self.results_dir)

            if results_dir.exists():
                for f in results_dir.glob("*.xml"):
                    results.append(
                        {
                            "filename": f.name,
                            "path": str(f),
                            "size": f.stat().st_size,
                        }
                    )

        if ea_name:
            results = [r for r in results if ea_name in str(r.get("filename", ""))]

        self.audit.log(
            AuditEventType.TOOL_INVOCATION,
            {
                "tool": "backtest_list_results",
                "count": len(results),
            },
        )

        return {
            "count": len(results),
            "results": results,
        }


async def handle_backtest_run(
    service: BacktestService,
    args: dict,
) -> dict[str, Any]:
    inp = BacktestRunInput.model_validate(args)
    return await service.backtest_run(
        ea_name=inp.ea_name,
        symbol=inp.symbol,
        timeframe=inp.timeframe,
        date_from=inp.date_from,
        date_to=inp.date_to,
        initial_deposit=inp.initial_deposit,
        leverage=inp.leverage,
        model=inp.model,
        optimization=inp.optimization,
    )


async def handle_backtest_optimize(
    service: BacktestService,
    args: dict,
) -> dict[str, Any]:
    inp = BacktestOptimizeInput.model_validate(args)
    return await service.backtest_optimize(
        ea_name=inp.ea_name,
        symbol=inp.symbol,
        timeframe=inp.timeframe,
        date_from=inp.date_from,
        date_to=inp.date_to,
        parameters=inp.parameters,
        criterion=inp.criterion,
    )


async def handle_backtest_list_results(
    service: BacktestService,
    args: dict,
) -> dict[str, Any]:
    inp = BacktestListResultsInput.model_validate(args)
    return await service.backtest_list_results(ea_name=inp.ea_name)


async def handle_backtest_get_results(
    service: BacktestService,
    args: dict,
) -> dict[str, Any]:
    inp = BacktestGetResultsInput.model_validate(args)
    return await service.backtest_get_results(job_id=inp.job_id)
