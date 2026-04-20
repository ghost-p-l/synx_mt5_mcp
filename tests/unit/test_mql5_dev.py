"""Unit tests for MQL5 development tools."""

from unittest.mock import AsyncMock

import pytest

from synx_mt5.tools.mql5_dev import (
    MQL5CompileInput,
    MQL5ListFilesInput,
    MQL5ReadFileInput,
    MQL5RunScriptInput,
    MQL5Service,
    MQL5WriteFileInput,
    handle_mql5_compile,
    handle_mql5_list_files,
    handle_mql5_read_file,
    handle_mql5_run_script,
    handle_mql5_write_file,
)


class MockAuditEngine:
    def __init__(self):
        self.events = []

    def log(self, event_type, data):
        self.events.append((event_type, data))


class MockMetaEditorBridge:
    def __init__(self):
        self._files = {}

    def write_file(self, filename, content, overwrite):
        if filename in self._files and not overwrite:
            return {"written": False, "error": "File exists"}
        self._files[filename] = content
        return {"written": True, "size_bytes": len(content)}

    async def compile(self, filename, include_path=None):
        if filename not in self._files:
            return {"success": False, "errors": 1, "error": "File not found"}
        return {"success": True, "output_path": filename.replace(".mq5", ".ex5"), "warnings": 0}

    def list_files(self, directory="all", extension="all"):
        return {"files": list(self._files.keys()), "count": len(self._files)}

    def read_file(self, filename):
        if filename not in self._files:
            return None
        return {
            "filename": filename,
            "content": self._files[filename],
            "size_bytes": len(self._files[filename]),
        }


class NoMetaEditorBridge:
    """Bridge without MQL5 methods."""

    async def terminal_info(self):
        return {}


@pytest.fixture
def mock_audit():
    return MockAuditEngine()


@pytest.fixture
def mock_bridge():
    return MockMetaEditorBridge()


@pytest.fixture
def service(mock_bridge, mock_audit):
    return MQL5Service(bridge=mock_bridge, audit=mock_audit)


class TestMQL5Service:
    @pytest.mark.asyncio
    async def test_write_file(self, service, mock_audit):
        result = await service.mql5_write_file(
            filename="MyEA.mq5",
            source_code="//+------------------------------------------------------------------+\nvoid OnStart() {}\n//+------------------------------------------------------------------+",
            overwrite=False,
        )
        assert result["written"] is True
        assert result["size_bytes"] > 0

    @pytest.mark.asyncio
    async def test_compile_success(self, service, mock_audit):
        await service.mql5_write_file(
            "TestEA.mq5",
            "//+------------------------------------------------------------------+",
            overwrite=True,
        )
        service._compile_async = AsyncMock(
            return_value={"success": True, "output_path": "TestEA.ex5", "warnings": 0}
        )
        result = await service.mql5_compile("TestEA.mq5")
        assert result["success"] is True
        assert "TestEA.ex5" in result["output_path"]

    @pytest.mark.asyncio
    async def test_compile_missing_file(self, service, mock_audit):
        service._compile_async = AsyncMock(
            return_value={"success": False, "errors": 1, "error": "File not found"}
        )
        result = await service.mql5_compile("NonExistent.mq5")
        assert result["success"] is False
        assert result["errors"] == 1

    @pytest.mark.asyncio
    async def test_list_files(self, service, mock_audit):
        await service.mql5_write_file("EA1.mq5", "// code1", overwrite=True)
        await service.mql5_write_file("EA2.mq5", "// code2", overwrite=True)
        result = await service.mql5_list_files()
        assert result["count"] == 2
        assert "EA1.mq5" in result["files"]

    @pytest.mark.asyncio
    async def test_read_file(self, service, mock_audit):
        code = "//+------------------------------------------------------------------+\nvoid OnStart() {}\n//+------------------------------------------------------------------+"
        await service.mql5_write_file("ReadMe.mq5", code, overwrite=True)
        result = await service.mql5_read_file("ReadMe.mq5")
        assert result["filename"] == "ReadMe.mq5"
        assert result["content"] == code
        assert result["size_bytes"] == len(code)

    @pytest.mark.asyncio
    async def test_read_file_not_found(self, service, mock_audit):
        result = await service.mql5_read_file("NonExistent.mq5")
        assert result["error"] == "File not found"
        assert result["content"] is None

    @pytest.mark.asyncio
    async def test_run_script_no_ea_bridge(self, service, mock_audit):
        result = await service.mql5_run_script(chart_id=1, script_name="MyScript.mq5")
        assert result["executed"] is False
        assert "EA REST bridge" in result["result"]


class TestHandlerFunctions:
    @pytest.mark.asyncio
    async def test_handle_mql5_write_file(self, service):
        result = await handle_mql5_write_file(
            service,
            {
                "filename": "HandlerTest.mq5",
                "source_code": "//+------------------------------------------------------------------+",
                "overwrite": True,
            },
        )
        assert result["written"] is True

    @pytest.mark.asyncio
    async def test_handle_mql5_compile(self, service):
        await handle_mql5_write_file(
            service, {"filename": "CompileTest.mq5", "source_code": "// test", "overwrite": True}
        )
        service._compile_async = AsyncMock(
            return_value={"success": True, "output_path": "CompileTest.ex5", "warnings": 0}
        )
        result = await handle_mql5_compile(service, {"filename": "CompileTest.mq5"})
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_handle_mql5_list_files(self, service):
        await handle_mql5_write_file(
            service, {"filename": "File1.mq5", "source_code": "// code", "overwrite": True}
        )
        result = await handle_mql5_list_files(service, {"directory": "all", "extension": "mq5"})
        assert "files" in result

    @pytest.mark.asyncio
    async def test_handle_mql5_read_file(self, service):
        await handle_mql5_write_file(
            service,
            {"filename": "ReadHandle.mq5", "source_code": "// read test", "overwrite": True},
        )
        result = await handle_mql5_read_file(service, {"filename": "ReadHandle.mq5"})
        assert result["filename"] == "ReadHandle.mq5"

    @pytest.mark.asyncio
    async def test_handle_mql5_read_file_not_found(self, service):
        result = await handle_mql5_read_file(service, {"filename": "NoExist.mq5"})
        assert result["error"] == "File not found"

    @pytest.mark.asyncio
    async def test_handle_mql5_run_script(self, service):
        result = await handle_mql5_run_script(
            service, {"chart_id": 1, "script_name": "TestScript.mq5"}
        )
        assert result["chart_id"] == 1
        assert result["executed"] is False


class TestInputValidation:
    def test_write_file_input(self):
        inp = MQL5WriteFileInput.model_validate(
            {
                "filename": "my_ea.mq5",
                "source_code": "// code",
                "overwrite": False,
            }
        )
        assert inp.filename == "my_ea.mq5"
        assert inp.overwrite is False

    def test_write_file_requires_mq5_extension(self):
        with pytest.raises(Exception):  # noqa: B017
            MQL5WriteFileInput.model_validate(
                {"filename": "script.py", "source_code": "print('hi')"}
            )

    def test_write_file_allows_mqh(self):
        inp = MQL5WriteFileInput.model_validate(
            {"filename": "my_header.mqh", "source_code": "// header"}
        )
        assert inp.filename == "my_header.mqh"

    def test_compile_input(self):
        inp = MQL5CompileInput.model_validate({"filename": "EA.mq5"})
        assert inp.filename == "EA.mq5"
        assert inp.include_path is None

    def test_list_files_input_defaults(self):
        inp = MQL5ListFilesInput.model_validate({})
        assert inp.directory == "all"
        assert inp.extension == "all"

    def test_read_file_requires_mq5_or_mqh(self):
        inp = MQL5ReadFileInput.model_validate({"filename": "EA.mq5"})
        assert inp.filename == "EA.mq5"

    def test_read_file_rejects_txt(self):
        with pytest.raises(Exception):  # noqa: B017
            MQL5ReadFileInput.model_validate({"filename": "readme.txt"})

    def test_run_script_input(self):
        inp = MQL5RunScriptInput.model_validate(
            {"chart_id": 1, "script_name": "MyScript.mq5", "parameters": {"param1": 10}}
        )
        assert inp.chart_id == 1
        assert inp.script_name == "MyScript.mq5"
        assert inp.parameters == {"param1": 10}

    def test_run_script_invalid_chart_id(self):
        with pytest.raises(Exception):  # noqa: B017
            MQL5RunScriptInput.model_validate({"chart_id": 0, "script_name": "test.mq5"})
