"""Unit tests for chart control tools."""

import pytest

from synx_mt5.tools.chart_control import (
    ChartCloseInput,
    ChartIndicatorAddInput,
    ChartIndicatorListInput,
    ChartNavigateInput,
    ChartOpenInput,
    ChartScreenshotInput,
    ChartService,
    handle_chart_apply_template,
    handle_chart_close,
    handle_chart_indicator_add,
    handle_chart_indicator_list,
    handle_chart_list,
    handle_chart_navigate,
    handle_chart_open,
    handle_chart_save_template,
    handle_chart_screenshot,
    handle_chart_set_symbol_timeframe,
)


class MockAuditEngine:
    def __init__(self):
        self.events = []

    def log(self, event_type, data):
        self.events.append((event_type, data))


class MockBridge:
    def __init__(self):
        self._charts = [
            {"chart_id": 1, "symbol": "EURUSD", "timeframe": "H1"},
            {"chart_id": 2, "symbol": "GBPUSD", "timeframe": "M15"},
        ]

    async def ea_chart_list(self):
        return self._charts

    async def ea_chart_open(self, symbol, timeframe):
        new_id = max(c["chart_id"] for c in self._charts) + 1
        chart = {"chart_id": new_id, "symbol": symbol, "timeframe": timeframe}
        self._charts.append(chart)
        return chart

    async def ea_chart_close(self, chart_id):
        self._charts = [c for c in self._charts if c["chart_id"] != chart_id]
        return {"closed": True}

    async def ea_chart_screenshot(self, chart_id, width, height, align_to_right):
        return {"image_base64": "iVBORw0KGgoAAAANSUhEUgAAAAE="}

    async def ea_chart_set_symbol_timeframe(self, chart_id, symbol, timeframe):
        return {"chart_id": chart_id, "symbol": symbol, "timeframe": timeframe}

    async def ea_chart_apply_template(self, chart_id, template_name):
        return {"chart_id": chart_id, "template": template_name}

    async def ea_chart_save_template(self, chart_id, template_name):
        return {"chart_id": chart_id, "template": template_name, "saved": True}

    async def ea_chart_navigate(self, chart_id, position, shift):
        return {"chart_id": chart_id, "position": position, "shift": shift}

    async def ea_chart_indicator_add(self, chart_id, indicator_path, window, parameters):
        return {"chart_id": chart_id, "indicator": indicator_path, "handle": 42}

    async def ea_chart_indicator_list(self, chart_id, window):
        return [
            {"name": "MA", "handle": 10, "window": 0},
            {"name": "RSI", "handle": 20, "window": 1},
        ]


class NoEABridge:
    """Bridge without EA methods for testing graceful degradation."""

    async def terminal_info(self):
        return {}


@pytest.fixture
def mock_audit():
    return MockAuditEngine()


@pytest.fixture
def mock_bridge():
    return MockBridge()


@pytest.fixture
def no_ea_bridge():
    return NoEABridge()


@pytest.fixture
def service(mock_bridge, mock_audit):
    return ChartService(bridge=mock_bridge, audit=mock_audit)


class TestChartService:
    @pytest.mark.asyncio
    async def test_chart_list(self, service, mock_audit):
        result = await service.chart_list()
        assert result["count"] == 2
        assert len(result["charts"]) == 2
        assert result["charts"][0]["symbol"] == "EURUSD"

    @pytest.mark.asyncio
    async def test_chart_open(self, service, mock_audit):
        result = await service.chart_open(symbol="XAUUSD", timeframe="H4")
        assert result["symbol"] == "XAUUSD"
        assert result["timeframe"] == "H4"
        assert result["chart_id"] == 3

    @pytest.mark.asyncio
    async def test_chart_close(self, service, mock_audit):
        result = await service.chart_close(chart_id=1)
        assert result["chart_id"] == 1
        assert result["closed"] is True

    @pytest.mark.asyncio
    async def test_chart_screenshot(self, service, mock_audit):
        result = await service.chart_screenshot(chart_id=1, width=1920, height=1080)
        assert result["chart_id"] == 1
        assert result["width"] == 1920
        assert result["height"] == 1080
        assert "image_base64" in result

    @pytest.mark.asyncio
    async def test_chart_set_symbol_timeframe(self, service, mock_audit):
        result = await service.chart_set_symbol_timeframe(
            chart_id=1, symbol="USDJPY", timeframe="D1"
        )
        assert result["symbol"] == "USDJPY"
        assert result["timeframe"] == "D1"

    @pytest.mark.asyncio
    async def test_chart_apply_template(self, service, mock_audit):
        result = await service.chart_apply_template(chart_id=1, template_name="my_template")
        assert result["chart_id"] == 1

    @pytest.mark.asyncio
    async def test_chart_save_template(self, service, mock_audit):
        result = await service.chart_save_template(chart_id=1, template_name="saved.tpl")
        assert result["chart_id"] == 1
        assert result["template"] == "saved.tpl"

    @pytest.mark.asyncio
    async def test_chart_navigate(self, service, mock_audit):
        result = await service.chart_navigate(chart_id=1, position="end", shift=100)
        assert result["chart_id"] == 1
        assert "navigated" in result

    @pytest.mark.asyncio
    async def test_chart_indicator_add(self, service, mock_audit):
        result = await service.chart_indicator_add(
            chart_id=1, indicator_path="Examples\\Indicators\\MA.mq5", window=0
        )
        assert result["chart_id"] == 1
        assert result["handle"] == 42

    @pytest.mark.asyncio
    async def test_chart_indicator_list(self, service, mock_audit):
        result = await service.chart_indicator_list(chart_id=1, window=0)
        assert result["chart_id"] == 1
        assert len(result["indicators"]) == 2


class TestChartServiceNoEAMode:
    @pytest.mark.asyncio
    async def test_chart_list_no_ea(self, no_ea_bridge, mock_audit):
        service = ChartService(bridge=no_ea_bridge, audit=mock_audit)
        result = await service.chart_list()
        assert result["count"] == 0
        assert result["charts"] == []

    @pytest.mark.asyncio
    async def test_chart_open_requires_ea(self, no_ea_bridge, mock_audit):
        service = ChartService(bridge=no_ea_bridge, audit=mock_audit)
        with pytest.raises(NotImplementedError):
            await service.chart_open(symbol="EURUSD", timeframe="H1")

    @pytest.mark.asyncio
    async def test_chart_close_requires_ea(self, no_ea_bridge, mock_audit):
        service = ChartService(bridge=no_ea_bridge, audit=mock_audit)
        with pytest.raises(NotImplementedError):
            await service.chart_close(chart_id=1)


class TestHandlerFunctions:
    @pytest.mark.asyncio
    async def test_handle_chart_list(self, service):
        result = await handle_chart_list(service, {})
        assert len(result["charts"]) == 2

    @pytest.mark.asyncio
    async def test_handle_chart_open(self, service):
        result = await handle_chart_open(service, {"symbol": "AUDUSD", "timeframe": "M30"})
        assert result["symbol"] == "AUDUSD"
        assert result["timeframe"] == "M30"

    @pytest.mark.asyncio
    async def test_handle_chart_close(self, service):
        result = await handle_chart_close(service, {"chart_id": 2})
        assert result["chart_id"] == 2

    @pytest.mark.asyncio
    async def test_handle_chart_screenshot(self, service):
        result = await handle_chart_screenshot(
            service, {"chart_id": 1, "width": 800, "height": 600}
        )
        assert result["chart_id"] == 1
        assert result["width"] == 800

    @pytest.mark.asyncio
    async def test_handle_chart_set_symbol_timeframe(self, service):
        result = await handle_chart_set_symbol_timeframe(
            service, {"chart_id": 1, "symbol": "USDCHF", "timeframe": "H2"}
        )
        assert result["symbol"] == "USDCHF"

    @pytest.mark.asyncio
    async def test_handle_chart_apply_template(self, service):
        result = await handle_chart_apply_template(
            service, {"chart_id": 1, "template_name": "my_tpl"}
        )
        assert result["chart_id"] == 1

    @pytest.mark.asyncio
    async def test_handle_chart_save_template(self, service):
        result = await handle_chart_save_template(
            service, {"chart_id": 1, "template_name": "save.tpl"}
        )
        assert result["chart_id"] == 1

    @pytest.mark.asyncio
    async def test_handle_chart_navigate(self, service):
        result = await handle_chart_navigate(
            service, {"chart_id": 1, "position": "begin", "shift": 50}
        )
        assert result["chart_id"] == 1
        assert "navigated" in result

    @pytest.mark.asyncio
    async def test_handle_chart_indicator_add(self, service):
        result = await handle_chart_indicator_add(
            service,
            {"chart_id": 1, "indicator_path": "MA.mq5", "window": 0},
        )
        assert result["chart_id"] == 1

    @pytest.mark.asyncio
    async def test_handle_chart_indicator_list(self, service):
        result = await handle_chart_indicator_list(service, {"chart_id": 1, "window": 0})
        assert result["chart_id"] == 1


class TestInputValidation:
    def test_chart_open_input(self):
        inp = ChartOpenInput.model_validate({"symbol": "eurusd", "timeframe": "H4"})
        assert inp.symbol == "EURUSD"
        assert inp.timeframe == "H4"

    def test_chart_close_input_invalid_chart_id(self):
        with pytest.raises(ValueError):
            ChartCloseInput.model_validate({"chart_id": 0})

    def test_chart_screenshot_input_defaults(self):
        inp = ChartScreenshotInput.model_validate({"chart_id": 1})
        assert inp.width == 1280
        assert inp.height == 720
        assert inp.align_to_right is True

    def test_chart_screenshot_width_bounds(self):
        inp = ChartScreenshotInput.model_validate({"chart_id": 1, "width": 2000})
        assert inp.width == 2000
        with pytest.raises(Exception):  # noqa: B017
            ChartScreenshotInput.model_validate({"chart_id": 1, "width": 200})

    def test_chart_navigate_input_defaults(self):
        inp = ChartNavigateInput.model_validate({"chart_id": 1})
        assert inp.position == "current"
        assert inp.shift == 0

    def test_chart_navigate_invalid_position(self):
        with pytest.raises(Exception):  # noqa: B017
            ChartNavigateInput.model_validate({"chart_id": 1, "position": "invalid"})

    def test_chart_navigate_valid_positions(self):
        for pos in ("begin", "end", "current"):
            inp = ChartNavigateInput.model_validate({"chart_id": 1, "position": pos})
            assert inp.position == pos

    def test_chart_indicator_add_input(self):
        inp = ChartIndicatorAddInput.model_validate(
            {"chart_id": 1, "indicator_path": "MA.mq5", "window": 0}
        )
        assert inp.indicator_path == "MA.mq5"
        assert inp.window == 0

    def test_chart_indicator_list_input(self):
        inp = ChartIndicatorListInput.model_validate({"chart_id": 1})
        assert inp.chart_id == 1
