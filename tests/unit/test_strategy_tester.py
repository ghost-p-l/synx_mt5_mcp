"""Unit tests for strategy tester tools."""

import tempfile
from pathlib import Path

import pytest

from synx_mt5.tools.strategy_tester import (
    BacktestGetResultsInput,
    BacktestListResultsInput,
    BacktestOptimizeInput,
    BacktestRunInput,
    BacktestService,
    handle_backtest_get_results,
    handle_backtest_list_results,
    handle_backtest_optimize,
    handle_backtest_run,
)


class MockAuditEngine:
    def __init__(self):
        self.events = []

    def log(self, event_type, data):
        self.events.append((event_type, data))


class NoMetaEditorBridge:
    """Bridge without backtest methods."""

    async def terminal_info(self):
        return {}


class MetaEditorBridgeWithBacktest:
    """Bridge with backtest support."""

    async def metaeditor_backtest(
        self, ea_name, symbol, timeframe, date_from, date_to, initial_deposit, leverage, model
    ):
        return {"started": True, "job_id": "bt_test123"}


@pytest.fixture
def mock_audit():
    return MockAuditEngine()


@pytest.fixture
def no_meta_bridge():
    return NoMetaEditorBridge()


@pytest.fixture
def with_meta_bridge():
    return MetaEditorBridgeWithBacktest()


@pytest.fixture
def tmp_results_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "MyEA_20240101_20240131.xml").write_text("<results/>")
        (Path(tmpdir) / "OtherEA_20240101_20240131.xml").write_text("<results/>")
        yield tmpdir


class TestBacktestService:
    @pytest.mark.asyncio
    async def test_backtest_run_no_ea(self, no_meta_bridge, mock_audit):
        service = BacktestService(bridge=no_meta_bridge, audit=mock_audit)
        result = await service.backtest_run(
            ea_name="TestEA",
            symbol="EURUSD",
            timeframe="H1",
            date_from="2024-01-01",
            date_to="2024-01-31",
        )
        assert result["ea_name"] == "TestEA"
        assert result["symbol"] == "EURUSD"
        assert "job_id" in result
        assert result["status"] == "not_implemented"
        assert len(mock_audit.events) == 1

    @pytest.mark.asyncio
    async def test_backtest_run_with_ea(self, with_meta_bridge, mock_audit):
        service = BacktestService(bridge=with_meta_bridge, audit=mock_audit)
        result = await service.backtest_run(
            ea_name="TestEA",
            symbol="EURUSD",
            timeframe="H4",
            date_from="2024-01-01",
            date_to="2024-01-31",
            initial_deposit=50000.0,
            leverage=200,
            model="ohlc_m1",
            optimization=False,
        )
        assert result["ea_name"] == "TestEA"
        assert result["symbol"] == "EURUSD"
        assert result["status"] == "queued"
        assert len(mock_audit.events) == 1

    @pytest.mark.asyncio
    async def test_backtest_get_results_pending(self, no_meta_bridge, mock_audit):
        service = BacktestService(bridge=no_meta_bridge, audit=mock_audit)
        result = await service.backtest_get_results(job_id="bt_nonexistent")
        assert result["status"] == "no_results"

    @pytest.mark.asyncio
    async def test_backtest_get_results_with_data(self, no_meta_bridge, mock_audit):
        service = BacktestService(bridge=no_meta_bridge, audit=mock_audit)
        service._jobs["bt_abc123"] = {
            "status": "completed",
            "ea_name": "TestEA",
            "results": {"profit": 1500.0, "trades": 42},
        }
        result = await service.backtest_get_results(job_id="bt_abc123")
        assert result["profit"] == 1500.0
        assert result["trades"] == 42

    @pytest.mark.asyncio
    async def test_backtest_optimize(self, no_meta_bridge, mock_audit):
        service = BacktestService(bridge=no_meta_bridge, audit=mock_audit)
        result = await service.backtest_optimize(
            ea_name="OptEA",
            symbol="EURUSD",
            timeframe="M30",
            date_from="2024-01-01",
            date_to="2024-01-31",
            parameters=[
                {"name": "Period", "start": 10, "stop": 50, "step": 5},
                {"name": "Threshold", "start": 0, "stop": 1.0, "step": 0.1},
            ],
            criterion="balance",
        )
        assert result["status"] == "running"
        assert result["parameter_combinations"] == (40 // 5) * (10 // 1)
        assert len(mock_audit.events) == 1

    @pytest.mark.asyncio
    async def test_backtest_optimize_single_param(self, no_meta_bridge, mock_audit):
        service = BacktestService(bridge=no_meta_bridge, audit=mock_audit)
        result = await service.backtest_optimize(
            ea_name="SingleParamEA",
            symbol="EURUSD",
            timeframe="H1",
            date_from="2024-01-01",
            date_to="2024-01-31",
            parameters=[{"name": "Period", "start": 5, "stop": 20, "step": 1}],
        )
        assert result["parameter_combinations"] == 15

    @pytest.mark.asyncio
    async def test_backtest_list_results_empty(self, no_meta_bridge, mock_audit):
        service = BacktestService(bridge=no_meta_bridge, audit=mock_audit)
        result = await service.backtest_list_results()
        assert result["count"] == 0
        assert result["results"] == []

    @pytest.mark.asyncio
    async def test_backtest_list_results_with_files(
        self, no_meta_bridge, mock_audit, tmp_results_dir
    ):
        service = BacktestService(
            bridge=no_meta_bridge, audit=mock_audit, results_dir=tmp_results_dir
        )
        result = await service.backtest_list_results()
        assert result["count"] == 2

    @pytest.mark.asyncio
    async def test_backtest_list_results_filtered(
        self, no_meta_bridge, mock_audit, tmp_results_dir
    ):
        service = BacktestService(
            bridge=no_meta_bridge, audit=mock_audit, results_dir=tmp_results_dir
        )
        result = await service.backtest_list_results(ea_name="MyEA")
        assert result["count"] == 1
        assert "MyEA" in result["results"][0]["filename"]


class TestHandlerFunctions:
    @pytest.mark.asyncio
    async def test_handle_backtest_run(self, no_meta_bridge, mock_audit):
        service = BacktestService(bridge=no_meta_bridge, audit=mock_audit)
        result = await handle_backtest_run(
            service,
            {
                "ea_name": "HandlerTestEA",
                "symbol": "EURUSD",
                "timeframe": "H1",
                "date_from": "2024-01-01",
                "date_to": "2024-01-31",
                "initial_deposit": 10000.0,
                "leverage": 100,
                "model": "every_tick",
                "optimization": False,
            },
        )
        assert result["ea_name"] == "HandlerTestEA"
        assert "job_id" in result

    @pytest.mark.asyncio
    async def test_handle_backtest_optimize(self, no_meta_bridge, mock_audit):
        service = BacktestService(bridge=no_meta_bridge, audit=mock_audit)
        result = await handle_backtest_optimize(
            service,
            {
                "ea_name": "OptTestEA",
                "symbol": "EURUSD",
                "timeframe": "M15",
                "date_from": "2024-01-01",
                "date_to": "2024-01-31",
                "parameters": [{"name": "Period", "start": 5, "stop": 15, "step": 2}],
            },
        )
        assert result["status"] == "running"

    @pytest.mark.asyncio
    async def test_handle_backtest_list_results(self, no_meta_bridge, mock_audit, tmp_results_dir):
        service = BacktestService(
            bridge=no_meta_bridge, audit=mock_audit, results_dir=tmp_results_dir
        )
        result = await handle_backtest_list_results(service, {"ea_name": "MyEA"})
        assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_handle_backtest_get_results(self, no_meta_bridge, mock_audit):
        service = BacktestService(bridge=no_meta_bridge, audit=mock_audit)
        service._jobs["bt_test"] = {"status": "completed", "results": {"profit": 999.0}}
        result = await handle_backtest_get_results(service, {"job_id": "bt_test"})
        assert result["profit"] == 999.0


class TestInputValidation:
    def test_backtest_run_input_defaults(self):
        inp = BacktestRunInput.model_validate(
            {
                "ea_name": "TestEA",
                "symbol": "EURUSD",
                "date_from": "2024-01-01",
                "date_to": "2024-01-31",
            }
        )
        assert inp.timeframe == "H1"
        assert inp.initial_deposit == 10000.0
        assert inp.leverage == 100
        assert inp.model == "every_tick"
        assert inp.optimization is False

    def test_backtest_run_input_symbol_sanitization(self):
        inp = BacktestRunInput.model_validate(
            {
                "ea_name": "TestEA",
                "symbol": "eurusd",
                "date_from": "2024-01-01",
                "date_to": "2024-01-31",
            }
        )
        assert inp.symbol == "EURUSD"

    def test_backtest_run_input_invalid_model(self):
        with pytest.raises(Exception):  # noqa: B017
            BacktestRunInput.model_validate(
                {
                    "ea_name": "TestEA",
                    "symbol": "EURUSD",
                    "date_from": "2024-01-01",
                    "date_to": "2024-01-31",
                    "model": "invalid_model",
                }
            )

    def test_backtest_run_input_valid_models(self):
        for model in ("every_tick", "ohlc_m1", "open_prices"):
            inp = BacktestRunInput.model_validate(
                {
                    "ea_name": "TestEA",
                    "symbol": "EURUSD",
                    "date_from": "2024-01-01",
                    "date_to": "2024-01-31",
                    "model": model,
                }
            )
            assert inp.model == model

    def test_backtest_run_input_leverage_bounds(self):
        inp = BacktestRunInput.model_validate(
            {
                "ea_name": "TestEA",
                "symbol": "EURUSD",
                "date_from": "2024-01-01",
                "date_to": "2024-01-31",
                "leverage": 500,
            }
        )
        assert inp.leverage == 500

    def test_backtest_run_input_negative_deposit(self):
        with pytest.raises(Exception):  # noqa: B017
            BacktestRunInput.model_validate(
                {
                    "ea_name": "TestEA",
                    "symbol": "EURUSD",
                    "date_from": "2024-01-01",
                    "date_to": "2024-01-31",
                    "initial_deposit": -100.0,
                }
            )

    def test_backtest_optimize_input(self):
        inp = BacktestOptimizeInput.model_validate(
            {
                "ea_name": "OptEA",
                "symbol": "EURUSD",
                "date_from": "2024-01-01",
                "date_to": "2024-01-31",
                "parameters": [{"name": "Period", "start": 5, "stop": 20, "step": 1}],
            }
        )
        assert inp.ea_name == "OptEA"
        assert inp.criterion == "balance"
        assert len(inp.parameters) == 1

    def test_backtest_optimize_requires_parameters(self):
        with pytest.raises(Exception):  # noqa: B017
            BacktestOptimizeInput.model_validate(
                {
                    "ea_name": "OptEA",
                    "symbol": "EURUSD",
                    "date_from": "2024-01-01",
                    "date_to": "2024-01-31",
                    "parameters": [],
                }
            )

    def test_backtest_get_results_input(self):
        inp = BacktestGetResultsInput.model_validate({"job_id": "bt_abc123"})
        assert inp.job_id == "bt_abc123"
        assert inp.ea_name is None

    def test_backtest_list_results_input(self):
        inp = BacktestListResultsInput.model_validate({"ea_name": "MyEA"})
        assert inp.ea_name == "MyEA"
