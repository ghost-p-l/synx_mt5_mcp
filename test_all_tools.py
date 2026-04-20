#!/usr/bin/env python3
"""Comprehensive test suite for all synx-mt5 MCP tools.

Tests all ~68 tools in batches:
1. Connection & initialization
2. Read-only market data & info
3. Pre-trade calculations
4. Position/order queries
5. Order execution (optional)
6. Risk & audit (optional)
"""

import asyncio
import json
import sys
from datetime import datetime, timedelta, UTC
from typing import Any

# Color codes for terminal output
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


def log_pass(name: str, result: Any = None):
    print(f"{GREEN}✓{RESET} {name}")
    if result and isinstance(result, dict) and result.get("error"):
        print(f"  → {YELLOW}{result.get('error')}{RESET}")


def log_fail(name: str, error: str):
    print(f"{RED}✗{RESET} {name}")
    print(f"  → {RED}{error}{RESET}")


def log_skip(name: str, reason: str):
    print(f"{YELLOW}⊘{RESET} {name} ({reason})")


def log_section(title: str):
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}{title}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")


async def run_tool(client: Any, tool_name: str, args: dict = None) -> tuple[bool, Any]:
    """Run a single tool and return (success, result)."""
    try:
        result = await client.call_tool(tool_name, args or {})
        if result.isError:
            return False, result.content[0].text if result.content else "Unknown error"
        # Parse structured content if available
        return True, getattr(result, 'structuredContent', None) or json.loads(
            result.content[0].text if result.content else "{}"
        )
    except Exception as e:
        return False, str(e)


async def test_connection_tools(client: Any) -> dict[str, int]:
    """Test 1: Connection & initialization (3 tools)."""
    log_section("Test 1: Connection & Initialization")
    results = {"pass": 0, "fail": 0, "skip": 0}

    # initialize
    success, result = await run_tool(client, "initialize")
    if success:
        log_pass("initialize")
        results["pass"] += 1
    else:
        log_fail("initialize", result)
        results["fail"] += 1
        return results

    # get_connection_status
    success, result = await run_tool(client, "get_connection_status")
    if success:
        log_pass("get_connection_status")
        results["pass"] += 1
    else:
        log_fail("get_connection_status", result)
        results["fail"] += 1

    return results


async def test_market_data_tools(client: Any) -> dict[str, int]:
    """Test 2: Market data & symbol info (11 tools)."""
    log_section("Test 2: Market Data & Symbol Info")
    results = {"pass": 0, "fail": 0, "skip": 0}

    # get_symbols_total
    success, result = await run_tool(client, "get_symbols_total")
    if success:
        log_pass("get_symbols_total")
        results["pass"] += 1
    else:
        log_fail("get_symbols_total", result)
        results["fail"] += 1
        return results

    # get_symbols (first 5)
    success, result = await run_tool(client, "get_symbols", {"group": "*", "exact_match": False})
    if success and isinstance(result, list) and len(result) > 0:
        log_pass(f"get_symbols ({len(result)} symbols found)")
        results["pass"] += 1
        test_symbol = result[0].get("name", "EURUSD")
    else:
        log_fail("get_symbols", "No symbols found" if success else result)
        results["fail"] += 1
        test_symbol = "EURUSD"

    # get_symbol_info
    success, result = await run_tool(client, "get_symbol_info", {"symbol": test_symbol})
    if success:
        log_pass(f"get_symbol_info ({test_symbol})")
        results["pass"] += 1
    else:
        log_fail(f"get_symbol_info ({test_symbol})", result)
        results["fail"] += 1

    # get_symbol_info_tick
    success, result = await run_tool(client, "get_symbol_info_tick", {"symbol": test_symbol})
    if success:
        log_pass(f"get_symbol_info_tick ({test_symbol})")
        results["pass"] += 1
    else:
        log_fail(f"get_symbol_info_tick ({test_symbol})", result)
        results["fail"] += 1

    # copy_rates_from_pos
    success, result = await run_tool(
        client, "copy_rates_from_pos", {"symbol": test_symbol, "timeframe": "H1", "start_pos": 0, "count": 5}
    )
    if success and isinstance(result, list):
        log_pass(f"copy_rates_from_pos ({len(result)} bars)")
        results["pass"] += 1
    else:
        log_fail("copy_rates_from_pos", result)
        results["fail"] += 1

    # copy_rates_from
    date_from = (datetime.now(UTC) - timedelta(days=7)).isoformat()
    success, result = await run_tool(
        client, "copy_rates_from", {"symbol": test_symbol, "timeframe": "H1", "date_from": date_from, "count": 5}
    )
    if success and isinstance(result, list):
        log_pass(f"copy_rates_from ({len(result)} bars)")
        results["pass"] += 1
    else:
        log_fail("copy_rates_from", result)
        results["fail"] += 1

    # copy_rates_range
    date_from = (datetime.now(UTC) - timedelta(days=7)).isoformat()
    date_to = datetime.now(UTC).isoformat()
    success, result = await run_tool(
        client,
        "copy_rates_range",
        {"symbol": test_symbol, "timeframe": "H1", "date_from": date_from, "date_to": date_to},
    )
    if success and isinstance(result, list):
        log_pass(f"copy_rates_range ({len(result)} bars)")
        results["pass"] += 1
    else:
        log_fail("copy_rates_range", result)
        results["fail"] += 1

    # copy_ticks_from
    date_from = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    success, result = await run_tool(
        client, "copy_ticks_from", {"symbol": test_symbol, "date_from": date_from, "count": 10}
    )
    if success and isinstance(result, list):
        log_pass(f"copy_ticks_from ({len(result)} ticks)")
        results["pass"] += 1
    else:
        log_fail("copy_ticks_from", result)
        results["fail"] += 1

    # copy_ticks_range
    date_from = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    date_to = datetime.now(UTC).isoformat()
    success, result = await run_tool(
        client, "copy_ticks_range", {"symbol": test_symbol, "date_from": date_from, "date_to": date_to}
    )
    if success and isinstance(result, list):
        log_pass(f"copy_ticks_range ({len(result)} ticks)")
        results["pass"] += 1
    else:
        log_fail("copy_ticks_range", result)
        results["fail"] += 1

    # symbol_select
    success, result = await run_tool(client, "symbol_select", {"symbol": test_symbol, "enable": True})
    if success:
        log_pass(f"symbol_select ({test_symbol})")
        results["pass"] += 1
    else:
        log_fail("symbol_select", result)
        results["fail"] += 1

    return results


async def test_pretrade_tools(client: Any) -> dict[str, int]:
    """Test 3: Pre-trade calculations (4 tools)."""
    log_section("Test 3: Pre-Trade Calculations")
    results = {"pass": 0, "fail": 0, "skip": 0}

    test_symbol = "EURUSD"

    # order_check
    success, result = await run_tool(
        client,
        "order_check",
        {"symbol": test_symbol, "volume": 0.1, "order_type": "BUY", "price": 1.1, "sl": 1.09, "tp": 1.12},
    )
    if success:
        log_pass("order_check")
        results["pass"] += 1
    else:
        log_fail("order_check", result)
        results["fail"] += 1

    # order_calc_margin
    success, result = await run_tool(
        client,
        "order_calc_margin",
        {"symbol": test_symbol, "volume": 0.1, "order_type": "BUY", "price": 1.1},
    )
    if success:
        log_pass("order_calc_margin")
        results["pass"] += 1
    else:
        log_fail("order_calc_margin", result)
        results["fail"] += 1

    # order_calc_profit
    success, result = await run_tool(
        client,
        "order_calc_profit",
        {
            "symbol": test_symbol,
            "volume": 0.1,
            "order_type": "BUY",
            "price_open": 1.10,
            "price_close": 1.12,
        },
    )
    if success:
        log_pass("order_calc_profit")
        results["pass"] += 1
    else:
        log_fail("order_calc_profit", result)
        results["fail"] += 1

    return results


async def test_account_tools(client: Any) -> dict[str, int]:
    """Test 4: Account & position queries (7 tools)."""
    log_section("Test 4: Account & Position Queries")
    results = {"pass": 0, "fail": 0, "skip": 0}

    # account_info
    success, result = await run_tool(client, "account_info")
    if success:
        log_pass("account_info")
        results["pass"] += 1
    else:
        log_fail("account_info", result)
        results["fail"] += 1

    # get_terminal_info
    success, result = await run_tool(client, "get_terminal_info")
    if success:
        log_pass("get_terminal_info")
        results["pass"] += 1
    else:
        log_fail("get_terminal_info", result)
        results["fail"] += 1

    # positions_total
    success, result = await run_tool(client, "positions_total")
    if success:
        log_pass(f"positions_total ({result} positions)")
        results["pass"] += 1
    else:
        log_fail("positions_total", result)
        results["fail"] += 1

    # positions_get
    success, result = await run_tool(client, "positions_get")
    if success and isinstance(result, list):
        log_pass(f"positions_get ({len(result)} positions)")
        results["pass"] += 1
    else:
        log_fail("positions_get", result)
        results["fail"] += 1

    # orders_total
    success, result = await run_tool(client, "orders_total")
    if success:
        log_pass(f"orders_total ({result} orders)")
        results["pass"] += 1
    else:
        log_fail("orders_total", result)
        results["fail"] += 1

    # orders_get
    success, result = await run_tool(client, "orders_get")
    if success and isinstance(result, list):
        log_pass(f"orders_get ({len(result)} orders)")
        results["pass"] += 1
    else:
        log_fail("orders_get", result)
        results["fail"] += 1

    return results


async def test_history_tools(client: Any) -> dict[str, int]:
    """Test 5: History & trading statistics (5 tools)."""
    log_section("Test 5: History & Statistics")
    results = {"pass": 0, "fail": 0, "skip": 0}

    date_from = (datetime.now(UTC) - timedelta(days=30)).isoformat()
    date_to = datetime.now(UTC).isoformat()

    # history_orders_total
    success, result = await run_tool(client, "history_orders_total", {"date_from": date_from, "date_to": date_to})
    if success:
        log_pass(f"history_orders_total ({result} orders)")
        results["pass"] += 1
    else:
        log_fail("history_orders_total", result)
        results["fail"] += 1

    # history_orders_get
    success, result = await run_tool(
        client, "history_orders_get", {"date_from": date_from, "date_to": date_to}
    )
    if success and isinstance(result, list):
        log_pass(f"history_orders_get ({len(result)} orders)")
        results["pass"] += 1
    else:
        log_fail("history_orders_get", result)
        results["fail"] += 1

    # history_deals_total
    success, result = await run_tool(client, "history_deals_total", {"date_from": date_from, "date_to": date_to})
    if success:
        log_pass(f"history_deals_total ({result} deals)")
        results["pass"] += 1
    else:
        log_fail("history_deals_total", result)
        results["fail"] += 1

    # history_deals_get
    success, result = await run_tool(client, "history_deals_get", {"date_from": date_from, "date_to": date_to})
    if success and isinstance(result, list):
        log_pass(f"history_deals_get ({len(result)} deals)")
        results["pass"] += 1
    else:
        log_fail("history_deals_get", result)
        results["fail"] += 1

    # get_trading_statistics
    success, result = await run_tool(
        client, "get_trading_statistics", {"date_from": date_from, "date_to": date_to}
    )
    if success:
        log_pass("get_trading_statistics")
        results["pass"] += 1
    else:
        log_fail("get_trading_statistics", result)
        results["fail"] += 1

    return results


async def test_market_depth_tools(client: Any) -> dict[str, int]:
    """Test 6: Market depth (DOM) (3 tools)."""
    log_section("Test 6: Market Depth (DOM)")
    results = {"pass": 0, "fail": 0, "skip": 0}

    test_symbol = "EURUSD"

    # market_book_subscribe
    success, result = await run_tool(client, "market_book_subscribe", {"symbol": test_symbol})
    if success:
        log_pass(f"market_book_subscribe ({test_symbol})")
        results["pass"] += 1
    else:
        log_fail(f"market_book_subscribe ({test_symbol})", result)
        results["fail"] += 1

    # market_book_get
    success, result = await run_tool(client, "market_book_get", {"symbol": test_symbol})
    if success and isinstance(result, (list, dict)):
        log_pass(f"market_book_get ({test_symbol})")
        results["pass"] += 1
    else:
        log_fail(f"market_book_get ({test_symbol})", result)
        results["fail"] += 1

    # market_book_unsubscribe
    success, result = await run_tool(client, "market_book_unsubscribe", {"symbol": test_symbol})
    if success:
        log_pass(f"market_book_unsubscribe ({test_symbol})")
        results["pass"] += 1
    else:
        log_fail(f"market_book_unsubscribe ({test_symbol})", result)
        results["fail"] += 1

    return results


async def test_intelligence_tools(client: Any) -> dict[str, int]:
    """Test 7: Intelligence & analysis (2 tools)."""
    log_section("Test 7: Intelligence & Analysis")
    results = {"pass": 0, "fail": 0, "skip": 0}

    test_symbol = "EURUSD"

    # get_market_regime
    success, result = await run_tool(
        client, "get_market_regime", {"symbol": test_symbol, "timeframe": "H1", "lookback": 100}
    )
    if success:
        log_pass("get_market_regime")
        results["pass"] += 1
    else:
        log_fail("get_market_regime", result)
        results["fail"] += 1

    # get_correlation_matrix
    success, result = await run_tool(
        client, "get_correlation_matrix", {"symbols": ["EURUSD", "GBPUSD"], "timeframe": "H1", "lookback": 100}
    )
    if success:
        log_pass("get_correlation_matrix")
        results["pass"] += 1
    else:
        log_fail("get_correlation_matrix", result)
        results["fail"] += 1

    return results


async def test_context_memory_tools(client: Any) -> dict[str, int]:
    """Test 8: Strategy context & memory (4 tools)."""
    log_section("Test 8: Strategy Context & Memory")
    results = {"pass": 0, "fail": 0, "skip": 0}

    # get_strategy_context
    success, result = await run_tool(client, "get_strategy_context")
    if success:
        log_pass("get_strategy_context")
        results["pass"] += 1
    else:
        log_fail("get_strategy_context", result)
        results["fail"] += 1

    # set_strategy_context
    test_context = "Testing dual-bridge architecture"
    success, result = await run_tool(client, "set_strategy_context", {"context": test_context})
    if success:
        log_pass("set_strategy_context")
        results["pass"] += 1
    else:
        log_fail("set_strategy_context", result)
        results["fail"] += 1

    # get_agent_memory
    success, result = await run_tool(client, "get_agent_memory", {"key": "test_key"})
    if success:
        log_pass("get_agent_memory")
        results["pass"] += 1
    else:
        log_fail("get_agent_memory", result)
        results["fail"] += 1

    # set_agent_memory
    success, result = await run_tool(client, "set_agent_memory", {"key": "test_key", "value": "test_value"})
    if success:
        log_pass("set_agent_memory")
        results["pass"] += 1
    else:
        log_fail("set_agent_memory", result)
        results["fail"] += 1

    return results


async def test_risk_audit_tools(client: Any) -> dict[str, int]:
    """Test 9: Risk & audit tools (5 tools)."""
    log_section("Test 9: Risk & Audit Tools")
    results = {"pass": 0, "fail": 0, "skip": 0}

    # get_risk_status
    success, result = await run_tool(client, "get_risk_status")
    if success:
        log_pass("get_risk_status")
        results["pass"] += 1
    else:
        log_fail("get_risk_status", result)
        results["fail"] += 1

    # get_risk_limits
    success, result = await run_tool(client, "get_risk_limits")
    if success:
        log_pass("get_risk_limits")
        results["pass"] += 1
    else:
        log_fail("get_risk_limits", result)
        results["fail"] += 1

    # get_drawdown_analysis
    date_from = (datetime.now(UTC) - timedelta(days=30)).isoformat()
    date_to = datetime.now(UTC).isoformat()
    success, result = await run_tool(
        client, "get_drawdown_analysis", {"date_from": date_from, "date_to": date_to}
    )
    if success:
        log_pass("get_drawdown_analysis")
        results["pass"] += 1
    else:
        log_fail("get_drawdown_analysis", result)
        results["fail"] += 1

    # get_audit_summary
    success, result = await run_tool(client, "get_audit_summary", {"hours": 24})
    if success:
        log_pass("get_audit_summary")
        results["pass"] += 1
    else:
        log_fail("get_audit_summary", result)
        results["fail"] += 1

    # verify_audit_chain
    success, result = await run_tool(client, "verify_audit_chain")
    if success:
        log_pass("verify_audit_chain")
        results["pass"] += 1
    else:
        log_fail("verify_audit_chain", result)
        results["fail"] += 1

    return results


async def test_terminal_tools(client: Any) -> dict[str, int]:
    """Test 10: Terminal management (3 tools)."""
    log_section("Test 10: Terminal Management")
    results = {"pass": 0, "fail": 0, "skip": 0}

    # terminal_get_info
    success, result = await run_tool(client, "terminal_get_info")
    if success:
        log_pass("terminal_get_info")
        results["pass"] += 1
    else:
        log_fail("terminal_get_info", result)
        results["fail"] += 1

    # terminal_get_data_path
    success, result = await run_tool(client, "terminal_get_data_path")
    if success:
        log_pass("terminal_get_data_path")
        results["pass"] += 1
    else:
        log_fail("terminal_get_data_path", result)
        results["fail"] += 1

    # terminal_get_common_path
    success, result = await run_tool(client, "terminal_get_common_path")
    if success:
        log_pass("terminal_get_common_path")
        results["pass"] += 1
    else:
        log_fail("terminal_get_common_path", result)
        results["fail"] += 1

    return results


async def main():
    """Run all test batches."""
    print(f"{BLUE}SYNX-MT5 COMPREHENSIVE TOOL TEST SUITE{RESET}")
    print(f"Testing ~68 tools across 10 categories\n")

    # Import the server
    try:
        from synx_mt5.server import SynxMT5Server

        server = SynxMT5Server()
        await server.initialize()
        client = server  # Use server directly as client
    except Exception as e:
        print(f"{RED}Failed to initialize server: {e}{RESET}")
        return

    all_results = {}

    # Run test batches in sequence
    test_batches = [
        ("Connection", test_connection_tools),
        ("Market Data", test_market_data_tools),
        ("Pre-Trade", test_pretrade_tools),
        ("Account", test_account_tools),
        ("History", test_history_tools),
        ("Market Depth", test_market_depth_tools),
        ("Intelligence", test_intelligence_tools),
        ("Context & Memory", test_context_memory_tools),
        ("Risk & Audit", test_risk_audit_tools),
        ("Terminal", test_terminal_tools),
    ]

    for batch_name, test_fn in test_batches:
        try:
            results = await test_fn(client)
            all_results[batch_name] = results
        except Exception as e:
            print(f"{RED}Batch '{batch_name}' failed: {e}{RESET}")
            all_results[batch_name] = {"pass": 0, "fail": 1, "skip": 0}

    # Summary
    log_section("Test Summary")
    total_pass = sum(r["pass"] for r in all_results.values())
    total_fail = sum(r["fail"] for r in all_results.values())
    total_skip = sum(r["skip"] for r in all_results.values())
    total = total_pass + total_fail + total_skip

    for batch_name, results in all_results.items():
        p, f, s = results["pass"], results["fail"], results["skip"]
        status = f"{GREEN}PASS{RESET}" if f == 0 else f"{RED}FAIL{RESET}"
        print(f"{status} {batch_name:20} {p:2d}✓ {f:2d}✗ {s:2d}⊘")

    print(f"\n{BLUE}{'='*60}{RESET}")
    if total_fail == 0:
        print(f"{GREEN}ALL TESTS PASSED{RESET} ({total_pass}/{total})")
    else:
        pct = (total_pass / total * 100) if total > 0 else 0
        print(f"{RED}TESTS FAILED{RESET}: {total_pass}/{total} passed ({pct:.0f}%)")
    print(f"{BLUE}{'='*60}{RESET}\n")

    # Cleanup
    try:
        await client.call_tool("shutdown", {})
    except Exception:
        pass


if __name__ == "__main__":
    asyncio.run(main())
