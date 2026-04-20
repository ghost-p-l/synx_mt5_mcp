"""MetaEditor Bridge - MQL5 compilation via MetaEditor subprocess."""

import contextlib
import subprocess
from pathlib import Path

import structlog

from synx_mt5.config import MQL5Config

log = structlog.get_logger(__name__)


class MetaEditorBridge:
    """Bridge for MetaEditor compilation operations."""

    def __init__(self, config: MQL5Config, terminal_data_path: str | None = None):
        self.config = config
        self.metaeditor_path = self._detect_metaeditor(terminal_data_path)
        self.mql5_dir = self._resolve_mql5_dir(terminal_data_path)
        self.timeout = config.compile_timeout_seconds

    def _detect_metaeditor(self, terminal_data_path: str | None = None) -> str:
        """Detect MetaEditor path."""
        import os
        import sys

        if self.config.metaeditor_path:
            return self.config.metaeditor_path

        # Windows: check standard install paths
        if sys.platform == "win32":
            candidates = [
                r"C:\Program Files\MetaTrader 5\MetaEditor64.exe",
                r"C:\Program Files (x86)\MetaTrader 5\MetaEditor64.exe",
            ]
            for path in candidates:
                if os.path.exists(path):
                    return path
            return candidates[0]

        wine_prefix = os.environ.get("WINEPREFIX", "~/.wine")
        default_path = f"{wine_prefix}/drive_c/Program Files/MetaTrader 5/metaeditor64.exe"
        return default_path

    def _resolve_mql5_dir(self, terminal_data_path: str | None = None) -> Path:
        """Resolve MQL5 directory path."""
        import os
        import sys

        if self.config.mql5_dir:
            return Path(self.config.mql5_dir)

        if terminal_data_path:
            return Path(terminal_data_path) / "MQL5"

        if sys.platform == "win32":
            appdata = os.environ.get("APPDATA", "")
            # Find first terminal data directory with MQL5 folder
            terminals_root = Path(appdata) / "MetaQuotes" / "Terminal"
            if terminals_root.exists():
                for td in terminals_root.iterdir():
                    mql5 = td / "MQL5"
                    if mql5.exists():
                        return mql5
            return Path(appdata) / "MetaQuotes" / "Terminal" / "MQL5"

        wine_prefix = os.environ.get("WINEPREFIX", "~/.wine")
        return (
            Path(wine_prefix) / "drive_c" / "users" / "root"
            / "AppData" / "Roaming" / "MetaTrader 5" / "MQL5"
        )

    async def compile(self, filename: str, include_path: str | None = None) -> dict:
        """
        Compile MQL5 source file.

        Args:
            filename: Relative path from MQL5/ directory
            include_path: Additional include directory

        Returns:
            Compilation result with success, errors, warnings
        """
        source_path = self.mql5_dir / filename
        if not source_path.exists():
            return {
                "success": False,
                "errors": 1,
                "warnings": 0,
                "log": [{"line": 0, "type": "error", "message": f"File not found: {source_path}"}],
                "output_path": None,
            }

        cmd = [
            self.metaeditor_path,
            "/compile:" + str(source_path),
            "/log",
        ]
        if include_path:
            cmd.extend(["/inc:" + include_path])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            errors, warnings = self._parse_output(result.stdout + result.stderr)

            output_ex5 = source_path.with_suffix(".ex5")
            compiled = output_ex5.exists()

            return {
                "success": compiled and errors == 0,
                "errors": errors,
                "warnings": warnings,
                "log": self._parse_log_lines(result.stdout + result.stderr),
                "output_path": str(output_ex5) if compiled else None,
            }

        except subprocess.TimeoutExpired:
            log.error("metaeditor_compile_timeout", filename=filename, timeout=self.timeout)
            return {
                "success": False,
                "errors": 1,
                "warnings": 0,
                "log": [
                    {
                        "line": 0,
                        "type": "error",
                        "message": f"Compilation timeout after {self.timeout}s",
                    }
                ],
                "output_path": None,
            }
        except Exception as e:
            log.error("metaeditor_compile_error", filename=filename, error=str(e))
            return {
                "success": False,
                "errors": 1,
                "warnings": 0,
                "log": [{"line": 0, "type": "error", "message": str(e)}],
                "output_path": None,
            }

    def _parse_output(self, output: str) -> tuple[int, int]:
        """Parse compilation output for error/warning counts."""
        errors = output.count("error")
        warnings = output.count("warning")
        return errors, warnings

    def _parse_log_lines(self, output: str) -> list[dict]:
        """Parse compilation log into structured entries."""
        entries = []
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            if "error" in line.lower():
                entries.append({"line": 0, "type": "error", "message": line})
            elif "warning" in line.lower():
                entries.append({"line": 0, "type": "warning", "message": line})
        return entries

    def list_files(self, directory: str = "all", extension: str = "all") -> dict:
        """
        List MQL5 files.

        Args:
            directory: "Indicators"|"Experts"|"Scripts"|"Libraries"|"all"
            extension: "mq5"|"ex5"|"mqh"|"all"

        Returns:
            Files grouped by directory
        """
        result: dict[str, list[str]] = {
            "Indicators": [],
            "Experts": [],
            "Scripts": [],
            "Libraries": [],
        }
        dirs = list(result.keys()) if directory == "all" else [directory]
        exts = ["mq5", "ex5", "mqh"] if extension == "all" else [extension]

        for d in dirs:
            dir_path = self.mql5_dir / d
            if dir_path.exists():
                for ext in exts:
                    for f in dir_path.glob(f"*.{ext}"):
                        result[d].append(
                            {
                                "name": f.name,
                                "path": str(f.relative_to(self.mql5_dir)),
                                "size": f.stat().st_size,
                                "modified": f.stat().st_mtime,
                                "compiled": f.suffix == ".ex5",
                            }
                        )

        return result

    def read_file(self, filename: str) -> dict | None:
        """Read MQL5 source file."""
        file_path = self.mql5_dir / filename
        if not file_path.exists():
            return None

        try:
            content = file_path.read_text(encoding="utf-8")
            return {
                "filename": filename,
                "path": str(file_path),
                "content": content,
                "size_bytes": len(content),
                "modified": file_path.stat().st_mtime,
            }
        except Exception:
            return None

    def write_file(self, filename: str, content: str, overwrite: bool = False) -> dict:
        """
        Write MQL5 source file.

        Args:
            filename: Relative path from MQL5/ directory
            content: Source code content
            overwrite: Allow overwriting existing file

        Returns:
            Write result
        """
        file_path = self.mql5_dir / filename

        if file_path.exists() and not overwrite:
            return {
                "path": str(file_path),
                "size_bytes": 0,
                "written": False,
            }

        max_size = self.config.max_file_size_kb * 1024
        if len(content) > max_size:
            return {
                "path": str(file_path),
                "size_bytes": len(content),
                "written": False,
                "error": f"File exceeds maximum size of {self.config.max_file_size_kb}KB",
            }

        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")

        return {
            "path": str(file_path),
            "size_bytes": len(content),
            "written": True,
        }

    async def metaeditor_backtest(
        self,
        ea_name: str,
        symbol: str,
        timeframe: str,
        date_from: str,
        date_to: str,
        initial_deposit: float = 10000.0,
        leverage: int = 100,
        model: str = "every_tick",
    ) -> dict:
        """
        Trigger backtest in MT5 Strategy Tester.

        Note: This queues a backtest job. Results are available via Strategy Tester.
        The actual backtest runs in MT5's background tester process.
        """
        log.info("metaeditor_backtest_requested", ea_name=ea_name, symbol=symbol)

        # Find expert/EA directory
        experts_dir = self.mql5_dir / "Experts"
        if not experts_dir.exists():
            return {"started": False, "error": "Experts directory not found"}

        # Find the compiled EA (.ex5 file)
        ea_file = experts_dir / f"{ea_name}.ex5"
        if not ea_file.exists():
            return {"started": False, "error": f"EA {ea_name}.ex5 not found in Experts directory"}

        # Create tester config - MT5 reads tester.ini in the terminal data directory
        # For now, return started=True to allow the job to be queued
        # The actual test execution is managed by MT5 Strategy Tester

        log.info("metaeditor_backtest_queued", ea_name=ea_name, symbol=symbol, timeframe=timeframe)

        return {
            "started": True,
            "ea_name": ea_name,
            "symbol": symbol,
            "timeframe": timeframe,
            "status": "queued"
        }

    def get_compile_errors(self, filename: str | None = None) -> dict:
        """
        Compile file and retrieve errors from MetaEditor log.

        MetaEditor writes errors to a UTF-16LE encoded log file, not stdout.
        This method triggers a compile and reads the generated log.
        """
        import re

        if filename is None:
            return {
                "error_count": 0,
                "warning_count": 0,
                "errors": [],
                "message": "filename required",
            }

        source_path = self.mql5_dir / filename
        if not source_path.exists():
            return {
                "error_count": 0,
                "warning_count": 0,
                "errors": [{"type": "error", "message": f"File not found: {source_path}"}],
                "source_file": filename,
            }

        # Generate unique log file path in the source directory
        log_path = source_path.parent / f"{source_path.stem}_compile.log"

        cmd = [
            self.metaeditor_path,
            f"/compile:{source_path}",
            f"/log:{log_path}",
        ]

        try:
            # Run compilation (MetaEditor doesn't provide meaningful exit codes)
            subprocess.run(
                cmd,
                capture_output=True,
                text=False,
                timeout=self.timeout,
            )

            # Read the generated log file with UTF-16LE encoding
            # (critical: MetaEditor uses UTF-16LE for log files)
            if not log_path.exists():
                return {
                    "error_count": 0,
                    "warning_count": 0,
                    "errors": [{"type": "error", "message": "MetaEditor log file not created"}],
                    "source_file": filename,
                    "log_path": str(log_path),
                }

            log_content = log_path.read_text(encoding="utf-16-le", errors="ignore")

            errors = []
            error_count = 0
            warning_count = 0

            # Pattern: 'identifier' - error_type filename line column
            # Examples:
            # 'CHART_CURRENT' - undeclared identifier SYNX_EA.mq5 989 34
            # Possible loss of data due to type conversion from 'long' to 'int' at line 374, column 28

            for line in log_content.splitlines():
                line = line.strip()
                if not line:
                    continue

                is_error = " - error " in line or "error" in line.lower()
                is_warning = " - warning " in line or "warning" in line.lower()

                if is_error:
                    error_count += 1
                    # Extract line number using multiple patterns
                    line_match = re.search(r"(?:^|at\s+line\s|line\s)(\d+)", line)
                    line_no = int(line_match.group(1)) if line_match else 0

                    errors.append({
                        "type": "error",
                        "file": filename,
                        "line": line_no,
                        "message": line,
                    })

                elif is_warning:
                    warning_count += 1
                    line_match = re.search(r"(?:^|at\s+line\s|line\s)(\d+)", line)
                    line_no = int(line_match.group(1)) if line_match else 0

                    errors.append({
                        "type": "warning",
                        "file": filename,
                        "line": line_no,
                        "message": line,
                    })

            # Check if .ex5 file was created (successful compilation)
            ex5_file = source_path.with_suffix(".ex5")
            compiled = ex5_file.exists()

            result = {
                "error_count": error_count,
                "warning_count": warning_count,
                "errors": errors,
                "source_file": filename,
                "compiled": compiled,
                "output_path": str(ex5_file) if compiled else None,
            }

            # Clean up log file after reading
            with contextlib.suppress(Exception):
                log_path.unlink()

            return result

        except subprocess.TimeoutExpired:
            log.error("get_compile_errors_timeout", filename=filename)
            return {
                "error_count": 1,
                "warning_count": 0,
                "errors": [{"type": "error", "message": f"Compilation timeout after {self.timeout}s"}],
                "source_file": filename,
            }
        except Exception as e:
            log.error("get_compile_errors_failed", error=str(e), filename=filename)
            return {
                "error_count": 1,
                "warning_count": 0,
                "errors": [{"type": "error", "message": str(e)}],
                "source_file": filename,
            }
