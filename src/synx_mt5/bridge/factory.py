"""Bridge factory for creating the appropriate MT5 bridge."""

from typing import TYPE_CHECKING

from synx_mt5.config import BridgeConfig

if TYPE_CHECKING:
    from synx_mt5.bridge.base import MT5Bridge


class BridgeFactory:
    """Factory for creating MT5 bridge instances."""

    @staticmethod
    def create(config: BridgeConfig) -> "MT5Bridge":
        """
        Create appropriate bridge based on configuration.

        Args:
            config: Bridge configuration

        Returns:
            MT5Bridge instance
        """
        mode = config.mode.lower()

        if mode == "python_com":
            from synx_mt5.bridge.python_com import PythonCOMBridge

            return PythonCOMBridge(config)

        elif mode == "ea_rest":
            from synx_mt5.bridge.ea_rest import EARestBridge

            return EARestBridge(config)

        elif mode == "wine":
            from synx_mt5.bridge.wine import WineBridge

            return WineBridge(config)

        elif mode == "ea_file":
            from synx_mt5.bridge.ea_file import EAFileBridge

            return EAFileBridge(config)

        elif mode == "composite":
            from synx_mt5.bridge.composite import CompositeBridge

            return CompositeBridge(config)

        else:
            raise ValueError(f"Unknown bridge mode: {mode}")
