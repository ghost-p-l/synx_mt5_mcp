"""Chart Control Tools - Chart operations via SYNX_EA REST bridge."""

from typing import Any

import structlog
from pydantic import BaseModel, Field, field_validator

from synx_mt5.audit.engine import AuditEngine, AuditEventType
from synx_mt5.security.injection_shield import sanitise_string

log = structlog.get_logger(__name__)


class ChartOpenInput(BaseModel):
    """Input for chart_open tool."""

    symbol: str = Field(min_length=1, max_length=32)
    timeframe: str = Field(default="H1")

    @field_validator("symbol")
    @classmethod
    def sanitize_symbol(cls, v: str) -> str:
        return sanitise_string(v, "chart_open:symbol").upper()


class ChartCloseInput(BaseModel):
    """Input for chart_close tool."""

    chart_id: int = Field(gt=0)


class ChartScreenshotInput(BaseModel):
    """Input for chart_screenshot tool."""

    chart_id: int = Field(gt=0)
    width: int = Field(default=1280, ge=320, le=3840)
    height: int = Field(default=720, ge=240, le=2160)
    align_to_right: bool = Field(default=True)


class ChartSetSymbolTimeframeInput(BaseModel):
    """Input for chart_set_symbol_timeframe tool."""

    chart_id: int = Field(gt=0)
    symbol: str | None = Field(default=None, max_length=32)
    timeframe: str | None = Field(default=None)


class ChartApplyTemplateInput(BaseModel):
    """Input for chart_apply_template tool."""

    chart_id: int = Field(gt=0)
    template_name: str = Field(min_length=1, max_length=64)


class ChartSaveTemplateInput(BaseModel):
    """Input for chart_save_template tool."""

    chart_id: int = Field(gt=0)
    template_name: str = Field(min_length=1, max_length=64)


class ChartNavigateInput(BaseModel):
    """Input for chart_navigate tool."""

    chart_id: int = Field(gt=0)
    position: str = Field(default="current")
    shift: int = Field(default=0)

    @field_validator("position")
    @classmethod
    def validate_position(cls, v: str) -> str:
        if v not in ("begin", "end", "current"):
            raise ValueError("position must be 'begin', 'end', or 'current'")
        return v


class ChartIndicatorAddInput(BaseModel):
    """Input for chart_indicator_add tool."""

    chart_id: int = Field(ge=0)
    indicator_path: str = Field(min_length=1, max_length=128)
    window: int = Field(default=0, ge=0)
    parameters: dict[str, Any] | None = None


class ChartIndicatorListInput(BaseModel):
    """Input for chart_indicator_list tool."""

    chart_id: int = Field(ge=0)
    window: int | None = Field(default=None)


class ChartAttachEAInput(BaseModel):
    """Input for chart_attach_ea tool."""

    chart_id: int = Field(gt=0)
    ea_name: str = Field(min_length=1, max_length=64)


class ChartRemoveEAInput(BaseModel):
    """Input for chart_remove_ea tool."""

    chart_id: int = Field(gt=0)


class ChartService:
    """
    Service layer for chart operations.

    Note: These operations require the EA REST bridge mode
    as they use SYNX_EA's chart control capabilities.
    """

    def __init__(
        self,
        bridge: Any,
        audit: AuditEngine,
    ):
        self.bridge = bridge
        self.audit = audit

    async def chart_list(self) -> dict[str, Any]:
        """List all currently open charts."""
        import structlog
        logger = structlog.get_logger(__name__)

        has_ea_chart_list = hasattr(self.bridge, "ea_chart_list")
        has_common_files = hasattr(self.bridge, "_common_files")

        logger.info("chart_list_called",
                    has_bridge_ea_chart_list=has_ea_chart_list,
                    has_common_files=has_common_files,
                    bridge_type=type(self.bridge).__name__)

        if has_ea_chart_list:
            try:
                charts = await self.bridge.ea_chart_list()
                logger.info("chart_list_from_bridge", charts=charts)
            except Exception as e:
                logger.error("chart_list_error", error=str(e))
                charts = []
        else:
            charts = []

        self.audit.log(
            AuditEventType.TOOL_INVOCATION,
            {
                "tool": "chart_list",
                "count": len(charts),
            },
        )

        return {
            "count": len(charts),
            "charts": charts,
        }

    async def chart_open(
        self,
        symbol: str,
        timeframe: str = "H1",
    ) -> dict[str, Any]:
        """Open a new chart window."""
        self.audit.log(
            AuditEventType.CHART_OPERATION,
            {
                "operation": "chart_open",
                "symbol": symbol,
                "timeframe": timeframe,
            },
        )

        if hasattr(self.bridge, "ea_chart_open"):
            result = await self.bridge.ea_chart_open(symbol, timeframe)
        else:
            raise NotImplementedError("chart_open requires EA REST bridge mode")

        return {
            "chart_id": result.get("chart_id", 0),
            "symbol": symbol,
            "timeframe": timeframe,
        }

    async def chart_close(self, chart_id: int) -> dict[str, Any]:
        """Close a chart by ID."""
        self.audit.log(
            AuditEventType.CHART_OPERATION,
            {
                "operation": "chart_close",
                "chart_id": chart_id,
            },
        )

        if hasattr(self.bridge, "ea_chart_close"):
            result = await self.bridge.ea_chart_close(chart_id)
        else:
            raise NotImplementedError("chart_close requires EA REST bridge mode")

        return {
            "chart_id": chart_id,
            "closed": result.get("closed", False),
        }

    async def chart_screenshot(
        self,
        chart_id: int,
        width: int = 1280,
        height: int = 720,
        align_to_right: bool = True,
    ) -> dict[str, Any]:
        """Capture chart as PNG image."""
        self.audit.log(
            AuditEventType.CHART_OPERATION,
            {
                "operation": "chart_screenshot",
                "chart_id": chart_id,
            },
        )

        if hasattr(self.bridge, "ea_chart_screenshot"):
            result = await self.bridge.ea_chart_screenshot(chart_id, width, height, align_to_right)
        else:
            raise NotImplementedError("chart_screenshot requires EA REST bridge mode")

        return {
            "chart_id": chart_id,
            "image_base64": result.get("image_base64", ""),
            "width": width,
            "height": height,
        }

    async def chart_set_symbol_timeframe(
        self,
        chart_id: int,
        symbol: str | None = None,
        timeframe: str | None = None,
    ) -> dict[str, Any]:
        """Change chart symbol and/or timeframe."""
        self.audit.log(
            AuditEventType.CHART_OPERATION,
            {
                "operation": "chart_set_symbol_timeframe",
                "chart_id": chart_id,
            },
        )

        if hasattr(self.bridge, "ea_chart_set_symbol_timeframe"):
            await self.bridge.ea_chart_set_symbol_timeframe(chart_id, symbol, timeframe)
        else:
            raise NotImplementedError("chart_set_symbol_timeframe requires EA REST bridge mode")

        return {
            "chart_id": chart_id,
            "symbol": symbol,
            "timeframe": timeframe,
        }

    async def chart_apply_template(
        self,
        chart_id: int,
        template_name: str,
    ) -> dict[str, Any]:
        """Apply saved .tpl template to chart."""
        self.audit.log(
            AuditEventType.CHART_OPERATION,
            {
                "operation": "chart_apply_template",
                "chart_id": chart_id,
                "template": template_name,
            },
        )

        if hasattr(self.bridge, "ea_chart_apply_template"):
            result = await self.bridge.ea_chart_apply_template(chart_id, template_name)
        else:
            raise NotImplementedError("chart_apply_template requires EA REST bridge mode")

        return {
            "chart_id": chart_id,
            "template": template_name,
            "applied": result.get("applied", False),
        }

    async def chart_navigate(
        self,
        chart_id: int,
        position: str = "current",
        shift: int = 0,
    ) -> dict[str, Any]:
        """Navigate chart scroll position."""
        self.audit.log(
            AuditEventType.CHART_OPERATION,
            {
                "operation": "chart_navigate",
                "chart_id": chart_id,
            },
        )

        if hasattr(self.bridge, "ea_chart_navigate"):
            result = await self.bridge.ea_chart_navigate(chart_id, position, shift)
        else:
            raise NotImplementedError("chart_navigate requires EA REST bridge mode")

        return {
            "chart_id": chart_id,
            "navigated": result.get("navigated", False),
        }

    async def chart_indicator_add(
        self,
        chart_id: int,
        indicator_path: str,
        window: int = 0,
        parameters: dict | None = None,
    ) -> dict[str, Any]:
        """Add indicator to chart."""
        self.audit.log(
            AuditEventType.CHART_OPERATION,
            {
                "operation": "chart_indicator_add",
                "chart_id": chart_id,
                "indicator": indicator_path,
            },
        )

        if hasattr(self.bridge, "ea_chart_indicator_add"):
            result = await self.bridge.ea_chart_indicator_add(
                chart_id, indicator_path, window, parameters or {}
            )
        else:
            raise NotImplementedError("chart_indicator_add requires EA REST bridge mode")

        if "error" in result:
            return {"chart_id": chart_id, "indicator": indicator_path,
                    "window": window, "handle": -1,
                    "error": result["error"], "code": result.get("code", 500)}

        return {
            "chart_id": chart_id,
            "indicator": indicator_path,
            "window": window,
            "handle": result.get("handle", -1),
            "success": result.get("success", False),
            "total_after": result.get("total_after", 0),
        }

    async def chart_indicator_list(
        self,
        chart_id: int,
        window: int | None = None,
    ) -> dict[str, Any]:
        """List indicators on chart."""
        self.audit.log(
            AuditEventType.CHART_OPERATION,
            {
                "operation": "chart_indicator_list",
                "chart_id": chart_id,
            },
        )

        if hasattr(self.bridge, "ea_chart_indicator_list"):
            indicators = await self.bridge.ea_chart_indicator_list(chart_id, window)
        else:
            indicators = []

        return {
            "chart_id": chart_id,
            "indicators": indicators,
        }

    async def chart_save_template(
        self,
        chart_id: int,
        template_name: str,
    ) -> dict[str, Any]:
        """Save chart configuration as a .tpl template."""
        self.audit.log(
            AuditEventType.CHART_OPERATION,
            {
                "operation": "chart_save_template",
                "chart_id": chart_id,
                "template": template_name,
            },
        )

        if hasattr(self.bridge, "ea_chart_save_template"):
            result = await self.bridge.ea_chart_save_template(chart_id, template_name)
        else:
            raise NotImplementedError("chart_save_template requires EA REST bridge mode")

        return {
            "chart_id": chart_id,
            "template": template_name,
            "saved": result.get("saved", False),
        }

    async def chart_attach_ea(
        self,
        chart_id: int,
        ea_name: str,
    ) -> dict[str, Any]:
        """Attach an Expert Advisor to a chart."""
        self.audit.log(
            AuditEventType.CHART_OPERATION,
            {
                "operation": "chart_attach_ea",
                "chart_id": chart_id,
                "ea_name": ea_name,
            },
        )

        if hasattr(self.bridge, "ea_chart_attach_ea"):
            result = await self.bridge.ea_chart_attach_ea(chart_id, ea_name)
        else:
            raise NotImplementedError("chart_attach_ea not available on this bridge")

        return {
            "chart_id": chart_id,
            "ea_name": ea_name,
            "attached": result.get("attached", False),
        }

    async def chart_remove_ea(
        self,
        chart_id: int,
    ) -> dict[str, Any]:
        """Remove Expert Advisor from a chart."""
        self.audit.log(
            AuditEventType.CHART_OPERATION,
            {
                "operation": "chart_remove_ea",
                "chart_id": chart_id,
            },
        )

        if hasattr(self.bridge, "ea_chart_remove_ea"):
            result = await self.bridge.ea_chart_remove_ea(chart_id)
        else:
            raise NotImplementedError("chart_remove_ea not available on this bridge")

        return {
            "chart_id": chart_id,
            "removed": result.get("removed", False),
        }


async def handle_chart_list(
    service: ChartService,
    args: dict,
) -> dict[str, Any]:
    return await service.chart_list()


async def handle_chart_open(
    service: ChartService,
    args: dict,
) -> dict[str, Any]:
    inp = ChartOpenInput.model_validate(args)
    return await service.chart_open(symbol=inp.symbol, timeframe=inp.timeframe)


async def handle_chart_close(
    service: ChartService,
    args: dict,
) -> dict[str, Any]:
    inp = ChartCloseInput.model_validate(args)
    return await service.chart_close(chart_id=inp.chart_id)


async def handle_chart_screenshot(
    service: ChartService,
    args: dict,
) -> dict[str, Any]:
    inp = ChartScreenshotInput.model_validate(args)
    return await service.chart_screenshot(
        chart_id=inp.chart_id,
        width=inp.width,
        height=inp.height,
        align_to_right=inp.align_to_right,
    )


async def handle_chart_set_symbol_timeframe(
    service: ChartService,
    args: dict,
) -> dict[str, Any]:
    inp = ChartSetSymbolTimeframeInput.model_validate(args)
    return await service.chart_set_symbol_timeframe(
        chart_id=inp.chart_id,
        symbol=inp.symbol,
        timeframe=inp.timeframe,
    )


async def handle_chart_apply_template(
    service: ChartService,
    args: dict,
) -> dict[str, Any]:
    inp = ChartApplyTemplateInput.model_validate(args)
    return await service.chart_apply_template(
        chart_id=inp.chart_id, template_name=inp.template_name
    )


async def handle_chart_save_template(
    service: ChartService,
    args: dict,
) -> dict[str, Any]:
    inp = ChartSaveTemplateInput.model_validate(args)
    return await service.chart_save_template(chart_id=inp.chart_id, template_name=inp.template_name)


async def handle_chart_navigate(
    service: ChartService,
    args: dict,
) -> dict[str, Any]:
    inp = ChartNavigateInput.model_validate(args)
    return await service.chart_navigate(
        chart_id=inp.chart_id,
        position=inp.position,
        shift=inp.shift,
    )


async def handle_chart_indicator_add(
    service: ChartService,
    args: dict,
) -> dict[str, Any]:
    inp = ChartIndicatorAddInput.model_validate(args)
    return await service.chart_indicator_add(
        chart_id=inp.chart_id,
        indicator_path=inp.indicator_path,
        window=inp.window,
        parameters=inp.parameters,
    )


async def handle_chart_indicator_list(
    service: ChartService,
    args: dict,
) -> dict[str, Any]:
    inp = ChartIndicatorListInput.model_validate(args)
    return await service.chart_indicator_list(chart_id=inp.chart_id, window=inp.window)


async def handle_chart_attach_ea(
    service: ChartService,
    args: dict,
) -> dict[str, Any]:
    inp = ChartAttachEAInput.model_validate(args)
    return await service.chart_attach_ea(chart_id=inp.chart_id, ea_name=inp.ea_name)


async def handle_chart_remove_ea(
    service: ChartService,
    args: dict,
) -> dict[str, Any]:
    inp = ChartRemoveEAInput.model_validate(args)
    return await service.chart_remove_ea(chart_id=inp.chart_id)
