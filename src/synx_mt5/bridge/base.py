"""Abstract base class for MT5 bridges."""

from abc import ABC, abstractmethod
from typing import Any


class MT5Bridge(ABC):
    """
    Abstract interface for MT5 bridge implementations.
    All bridges must implement these methods to provide MT5 connectivity.
    """

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to MT5 terminal. Returns True if successful."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from MT5 terminal."""
        pass

    @abstractmethod
    async def is_connected(self) -> bool:
        """Check if bridge is currently connected."""
        pass

    @abstractmethod
    async def account_info(self) -> dict[str, Any]:
        """Get account information."""
        pass

    @abstractmethod
    async def terminal_info(self) -> dict[str, Any]:
        """Get terminal information."""
        pass

    @abstractmethod
    async def symbol_info(self, symbol: str) -> dict[str, Any] | None:
        """Get symbol information."""
        pass

    @abstractmethod
    async def symbol_info_tick(self, symbol: str) -> dict[str, Any] | None:
        """Get current tick for symbol."""
        pass

    @abstractmethod
    async def symbols_total(self) -> int:
        """Get total number of symbols."""
        pass

    @abstractmethod
    async def symbols_get(self, group: str = "*") -> list[dict[str, Any]]:
        """Get symbols matching group filter."""
        pass

    @abstractmethod
    async def symbol_select(self, symbol: str, select: bool = True) -> bool:
        """Add or remove symbol from MarketWatch."""
        pass

    @abstractmethod
    async def copy_rates_from_pos(
        self, symbol: str, timeframe: str, start_pos: int, count: int
    ) -> list[dict[str, Any]]:
        """Copy rates from position."""
        pass

    @abstractmethod
    async def copy_rates_from(
        self, symbol: str, timeframe: str, date_from: str, count: int
    ) -> list[dict[str, Any]]:
        """Copy rates from datetime."""
        pass

    @abstractmethod
    async def copy_rates_range(
        self, symbol: str, timeframe: str, date_from: str, date_to: str
    ) -> list[dict[str, Any]]:
        """Copy rates in datetime range."""
        pass

    @abstractmethod
    async def copy_ticks_from(
        self, symbol: str, date_from: str, count: int, flags: str = "COPY_TICKS_ALL"
    ) -> list[dict[str, Any]]:
        """Copy ticks from datetime."""
        pass

    @abstractmethod
    async def copy_ticks_range(
        self, symbol: str, date_from: str, date_to: str, flags: str = "COPY_TICKS_ALL"
    ) -> list[dict[str, Any]]:
        """Copy ticks in datetime range."""
        pass

    @abstractmethod
    async def positions_total(self) -> int:
        """Get total number of open positions."""
        pass

    @abstractmethod
    async def positions_get(self, symbol: str = "", ticket: int = 0) -> list[dict[str, Any]]:
        """Get open positions."""
        pass

    @abstractmethod
    async def orders_total(self) -> int:
        """Get total number of pending orders."""
        pass

    @abstractmethod
    async def orders_get(self, symbol: str = "", ticket: int = 0) -> list[dict[str, Any]]:
        """Get pending orders."""
        pass

    @abstractmethod
    async def history_orders_total(self, date_from: str, date_to: str) -> int:
        """Get count of historical orders."""
        pass

    @abstractmethod
    async def history_orders_get(
        self, date_from: str, date_to: str, symbol: str = ""
    ) -> list[dict[str, Any]]:
        """Get historical orders."""
        pass

    @abstractmethod
    async def history_deals_total(self, date_from: str, date_to: str) -> int:
        """Get count of historical deals."""
        pass

    @abstractmethod
    async def history_deals_get(
        self, date_from: str, date_to: str, symbol: str = ""
    ) -> list[dict[str, Any]]:
        """Get historical deals."""
        pass

    @abstractmethod
    async def order_calc_margin(
        self, order_type: str, symbol: str, volume: float, price: float
    ) -> dict[str, Any] | None:
        """Calculate margin for order."""
        pass

    @abstractmethod
    async def order_calc_profit(
        self, order_type: str, symbol: str, volume: float, price_open: float, price_close: float
    ) -> dict[str, Any] | None:
        """Calculate profit for order."""
        pass

    @abstractmethod
    async def order_check(
        self,
        symbol: str,
        order_type: str,
        volume: float,
        price: float,
        sl: float = 0,
        tp: float = 0,
    ) -> dict[str, Any]:
        """Check if order request is valid."""
        pass

    @abstractmethod
    async def order_send(
        self,
        symbol: str,
        order_type: str,
        volume: float,
        price: float,
        sl: float = 0,
        tp: float = 0,
        magic: int = 0,
        comment: str = "",
    ) -> dict[str, Any]:
        """Send order to MT5."""
        pass

    @abstractmethod
    async def position_close(
        self, ticket: int, volume: float = 0, deviation: int = 20
    ) -> dict[str, Any]:
        """Close position."""
        pass

    @abstractmethod
    async def position_modify(self, ticket: int, sl: float, tp: float) -> dict[str, Any]:
        """Modify position SL/TP."""
        pass

    @abstractmethod
    async def order_modify(self, ticket: int, price: float, sl: float, tp: float) -> dict[str, Any]:
        """Modify pending order."""
        pass

    @abstractmethod
    async def order_cancel(self, ticket: int) -> dict[str, Any]:
        """Cancel pending order."""
        pass

    @abstractmethod
    async def market_book_add(self, symbol: str) -> bool:
        """Subscribe to market book (DOM)."""
        pass

    @abstractmethod
    async def market_book_get(self, symbol: str) -> list[dict[str, Any]] | None:
        """Get market book entries."""
        pass

    @abstractmethod
    async def market_book_release(self, symbol: str) -> bool:
        """Release market book subscription."""
        pass
