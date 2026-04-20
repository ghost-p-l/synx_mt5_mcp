"""MQL5 Development Tools - Source code management and compilation."""

from typing import Any

import structlog
from pydantic import BaseModel, Field, field_validator, model_validator

from synx_mt5.audit.engine import AuditEngine, AuditEventType
from synx_mt5.bridge.metaeditor import MetaEditorBridge
from synx_mt5.security.injection_shield import sanitise_string

log = structlog.get_logger(__name__)


class MQL5WriteFileInput(BaseModel):
    """Input for mql5_write_file tool."""

    filename: str = Field(min_length=1, max_length=128)
    source_code: str = Field(max_length=524288)
    overwrite: bool = Field(default=False)

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, v: str) -> str:
        if not v.endswith((".mq5", ".mqh")):
            raise ValueError("Filename must end with .mq5 or .mqh")
        sanitized = sanitise_string(v, "mql5_write:filename")
        return sanitized


class MQL5CompileInput(BaseModel):
    """Input for mql5_compile tool."""

    filename: str = Field(min_length=1, max_length=128)
    include_path: str | None = Field(default=None)


class MQL5ListFilesInput(BaseModel):
    """Input for mql5_list_files tool."""

    directory: str = Field(default="all")
    extension: str = Field(default="all")


class MQL5ReadFileInput(BaseModel):
    """Input for mql5_read_file tool."""

    filename: str = Field(min_length=1, max_length=128)

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, v: str) -> str:
        if not v.endswith((".mq5", ".mqh", ".ex5")):
            raise ValueError("Filename must end with .mq5, .mqh, or .ex5")
        return sanitise_string(v, "mql5_read:filename")


class MQL5RunScriptInput(BaseModel):
    """Input for mql5_run_script tool."""

    script_name: str = Field(min_length=1, max_length=64)
    symbol: str | None = Field(default=None, description="Symbol name (e.g. EURUSD)")
    period: int | None = Field(
        default=None, description="Timeframe in minutes (1,5,15,30,60,240,1440,10080,43200)"
    )
    chart_id: int | None = Field(
        default=None, description="Chart ID (alternative to symbol+period)"
    )
    parameters: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_chart_lookup(self):
        if self.chart_id is not None and self.chart_id <= 0:
            raise ValueError("chart_id must be a positive integer")
        return self


class MQL5GetCompileErrorsInput(BaseModel):
    """Input for mql5_get_compile_errors tool."""

    filename: str | None = Field(default=None, max_length=128, description="Optional: specific file to check")


class MQL5Service:
    """
    Service layer for MQL5 development operations.
    """

    def __init__(
        self,
        bridge: MetaEditorBridge,
        audit: AuditEngine,
    ):
        self.bridge = bridge
        self.audit = audit

    async def mql5_write_file(
        self,
        filename: str,
        source_code: str,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """Write MQL5 source code to terminal directory."""
        result = self.bridge.write_file(
            filename=filename,
            content=source_code,
            overwrite=overwrite,
        )

        self.audit.log(
            AuditEventType.TOOL_INVOCATION,
            {
                "tool": "mql5_write_file",
                "filename": filename,
                "size": result.get("size_bytes", 0),
                "written": result.get("written", False),
            },
        )

        return result

    async def mql5_compile(
        self,
        filename: str,
        include_path: str | None = None,
    ) -> dict[str, Any]:
        """Compile MQL5 source via MetaEditor."""
        self.audit.log(
            AuditEventType.TOOL_INVOCATION,
            {
                "tool": "mql5_compile",
                "filename": filename,
            },
        )

        result = await self._compile_async(filename, include_path)

        if result.get("success"):
            self.audit.log(
                AuditEventType.MQL5_COMPILE_SUCCESS,
                {
                    "filename": filename,
                    "output_path": result.get("output_path"),
                },
            )
        else:
            self.audit.log(
                AuditEventType.MQL5_COMPILE_ERROR,
                {
                    "filename": filename,
                    "errors": result.get("errors", 0),
                },
            )

        return result

    async def _compile_async(
        self,
        filename: str,
        include_path: str | None,
    ) -> dict[str, Any]:
        """Async wrapper for MetaEditor compile."""
        return await self.bridge.compile(filename, include_path)

    async def mql5_list_files(
        self,
        directory: str = "all",
        extension: str = "all",
    ) -> dict[str, Any]:
        """List MQL5 files in terminal directories."""
        result = self.bridge.list_files(directory, extension)

        self.audit.log(
            AuditEventType.TOOL_INVOCATION,
            {
                "tool": "mql5_list_files",
                "directory": directory,
            },
        )

        return result

    async def mql5_read_file(self, filename: str) -> dict[str, Any]:
        """Read MQL5 source file contents."""
        result = self.bridge.read_file(filename)

        if result is None:
            return {
                "filename": filename,
                "path": None,
                "content": None,
                "error": "File not found",
            }

        self.audit.log(
            AuditEventType.TOOL_INVOCATION,
            {
                "tool": "mql5_read_file",
                "filename": filename,
                "size": result.get("size_bytes", 0),
            },
        )

        return result

    async def mql5_run_script(
        self,
        script_name: str,
        symbol: str | None = None,
        period: int | None = None,
        chart_id: int | None = None,
        parameters: dict | None = None,
    ) -> dict[str, Any]:
        """Execute one-shot MQL5 script on chart."""
        target_chart_id = chart_id

        if (
            target_chart_id is None
            and symbol is not None
            and hasattr(self.bridge, "bridge")
            and hasattr(self.bridge.bridge, "chart_symbol_timeframe")
        ):
            try:
                charts = await self.bridge.bridge.chart_list()
                for c in charts:
                    if c.get("symbol") == symbol and (period is None or c.get("period") == period):
                        target_chart_id = c.get("chart_id")
                        break
            except Exception:
                pass

        self.audit.log(
            AuditEventType.TOOL_INVOCATION,
            {
                "tool": "mql5_run_script",
                "chart_id": target_chart_id,
                "script": script_name,
            },
        )

        if (
            target_chart_id is not None
            and hasattr(self.bridge, "bridge")
            and hasattr(self.bridge.bridge, "ea_run_script")
        ):
            result = await self.bridge.bridge.ea_run_script(
                target_chart_id, script_name, parameters or {}
            )
        elif target_chart_id is None:
            result = {
                "chart_id": target_chart_id,
                "script": script_name,
                "executed": False,
                "result": "No chart found for symbol/period. Provide chart_id or open a chart first.",
            }
        else:
            result = {
                "chart_id": target_chart_id,
                "script": script_name,
                "executed": False,
                "result": "Script execution requires EA REST bridge",
            }

        return result

    async def mql5_get_compile_errors(
        self,
        filename: str | None = None,
    ) -> dict[str, Any]:
        """Retrieve MetaEditor compilation errors."""
        result = self.bridge.get_compile_errors(filename)

        self.audit.log(
            AuditEventType.TOOL_INVOCATION,
            {
                "tool": "mql5_get_compile_errors",
                "filename": filename,
                "error_count": result.get("error_count", 0),
            },
        )

        return result


async def handle_mql5_write_file(
    service: MQL5Service,
    args: dict,
) -> dict[str, Any]:
    inp = MQL5WriteFileInput.model_validate(args)
    return await service.mql5_write_file(
        filename=inp.filename,
        source_code=inp.source_code,
        overwrite=inp.overwrite,
    )


async def handle_mql5_compile(
    service: MQL5Service,
    args: dict,
) -> dict[str, Any]:
    inp = MQL5CompileInput.model_validate(args)
    return await service.mql5_compile(
        filename=inp.filename,
        include_path=inp.include_path,
    )


async def handle_mql5_list_files(
    service: MQL5Service,
    args: dict,
) -> dict[str, Any]:
    inp = MQL5ListFilesInput.model_validate(args)
    return await service.mql5_list_files(
        directory=inp.directory,
        extension=inp.extension,
    )


async def handle_mql5_read_file(
    service: MQL5Service,
    args: dict,
) -> dict[str, Any]:
    inp = MQL5ReadFileInput.model_validate(args)
    return await service.mql5_read_file(filename=inp.filename)


async def handle_mql5_run_script(
    service: MQL5Service,
    args: dict,
) -> dict[str, Any]:
    inp = MQL5RunScriptInput.model_validate(args)
    return await service.mql5_run_script(
        script_name=inp.script_name,
        symbol=inp.symbol,
        period=inp.period,
        chart_id=inp.chart_id,
        parameters=inp.parameters,
    )


async def handle_mql5_get_compile_errors(
    service: MQL5Service,
    args: dict,
) -> dict[str, Any]:
    inp = MQL5GetCompileErrorsInput.model_validate(args)
    return await service.mql5_get_compile_errors(filename=inp.filename)
