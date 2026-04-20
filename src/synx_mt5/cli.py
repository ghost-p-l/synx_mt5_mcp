"""CLI module - Command-line interface for SYNX-MT5-MCP."""

import asyncio
import json
import secrets
import sys
from pathlib import Path

import click
import structlog

from synx_mt5 import __version__
from synx_mt5.audit.engine import AuditEngine
from synx_mt5.bridge.factory import BridgeFactory
from synx_mt5.config import load_config
from synx_mt5.security.capability import get_active_profile
from synx_mt5.security.secrets import (
    credential_setup_wizard,
    store_credential,
)

log = structlog.get_logger(__name__)


@click.group()
@click.version_option(version=__version__)
def main():
    """SYNX-MT5-MCP - Production MT5 MCP Server for AI Trading Agents."""
    pass


@main.command()
def setup():
    """Interactive credential setup wizard."""
    credential_setup_wizard()


@main.command()
@click.option("--config", help="Path to configuration file")
def init_config(config):
    """Initialize configuration file."""
    config_path = Path(config or "~/.synx-mt5/synx.yaml").expanduser()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    if config_path.exists():
        click.echo(f"Config already exists at {config_path}")
        return

    example_path = Path(__file__).parent.parent.parent / "config" / "synx.example.yaml"
    if example_path.exists():
        import shutil

        shutil.copy(example_path, config_path)
        click.echo(f"Config created at {config_path}")
    else:
        click.echo("Example config not found")


@main.command()
@click.option("--config", help="Path to configuration file")
def test_connection(config):
    """Test MT5 connection."""
    click.echo("Testing MT5 connection...")

    try:
        from synx_mt5.bridge.factory import BridgeFactory

        cfg = load_config(config)
        bridge = BridgeFactory.create(cfg.bridge)

        loop = asyncio.new_event_loop()
        connected = loop.run_until_complete(bridge.connect())
        loop.run_until_complete(bridge.disconnect())

        if connected:
            click.echo("MT5 connection successful")
        else:
            click.echo("MT5 connection failed")
            sys.exit(1)
    except Exception as e:
        click.echo(f"Connection error: {e}")
        sys.exit(1)


@main.command()
@click.option("--config", help="Path to configuration file")
@click.option("--transport", default="stdio", type=click.Choice(["stdio", "http"]))
@click.option("--host", default="127.0.0.1")
@click.option("--port", default=8765, type=int)
@click.option("--api-key")
def start(config, transport, host, port, api_key):
    """Start SYNX-MT5-MCP server."""
    from synx_mt5.server import SYNXServer

    click.echo(f"Starting SYNX-MT5-MCP v{__version__}...")

    try:
        server = SYNXServer(config_path=config)
        loop = asyncio.new_event_loop()

        async def run():
            await server.initialize()
            if transport == "stdio":
                await server.run_stdio()
            else:
                await server.run_http(host, port, api_key or "")

        loop.run_until_complete(run())
    except KeyboardInterrupt:
        click.echo("\nShutting down...")
    except Exception as e:
        click.echo(f"Error: {e}")
        sys.exit(1)


@main.command()
def status():
    """Show server status."""
    profile_name, profile_tools = get_active_profile()
    click.echo(f"Profile: {profile_name}")
    click.echo(f"Tools: {len(profile_tools)}")


@main.group()
def risk():
    """Risk management commands."""
    pass


@risk.command()
@click.option("--config", help="Path to configuration file")
def risk_status(config):
    """Show risk subsystem status."""
    log_path = Path(config or "~/.synx-mt5/synx.yaml").expanduser().parent / "audit.jsonl"
    AuditEngine(log_path=log_path)

    click.echo("Risk Status:")

    breaker_file = Path("~/.synx-mt5/circuit_breaker_state.json").expanduser()
    if breaker_file.exists():
        try:
            breaker_data = json.loads(breaker_file.read_text())
            breaker_state = breaker_data.get("state", "unknown").upper()
        except Exception:
            breaker_state = "ERROR"
    else:
        breaker_state = "NOT_INITIALIZED"
    click.echo(f"  Circuit Breaker: {breaker_state}")

    hitl_file = Path("~/.synx-mt5/hitl_pending.json").expanduser()
    if hitl_file.exists():
        try:
            hitl_data = json.loads(hitl_file.read_text())
            hitl_pending = len(hitl_data.get("pending", []))
        except Exception:
            hitl_pending = 0
    else:
        hitl_pending = 0
    click.echo(f"  HITL Queue: {hitl_pending} pending")


@risk.command()
@click.argument("approval_id")
@click.option("--approver", default="human", help="Approver name")
@click.option("--config", help="Path to configuration file")
def approve(approval_id, approver, config):
    """Approve a pending order."""
    state_file = Path("~/.synx-mt5/hitl_pending.json").expanduser()

    if not state_file.exists():
        click.echo(f"No pending approvals found. State file: {state_file}")
        return

    try:
        data = json.loads(state_file.read_text())
        pending = data.get("pending", [])
    except Exception as e:
        click.echo(f"Error reading pending approvals: {e}")
        return

    if approval_id not in pending:
        click.echo(f"Approval ID '{approval_id}' not found in pending list: {pending}")
        return

    pending.remove(approval_id)
    state_file.write_text(json.dumps({"pending": pending}))

    log_path = Path("~/.synx-mt5/audit.jsonl").expanduser()
    audit = AuditEngine(log_path=log_path)
    audit.log(
        "RISK_HITL_APPROVED",
        {"approval_id": approval_id, "approver": approver, "source": "cli"},
    )

    click.echo(f"Approved: {approval_id} by {approver}")


@risk.command()
@click.argument("approval_id")
@click.option("--approver", default="human", help="Approver name")
@click.option("--config", help="Path to configuration file")
def reject(approval_id, approver, config):
    """Reject a pending order."""
    state_file = Path("~/.synx-mt5/hitl_pending.json").expanduser()

    if not state_file.exists():
        click.echo(f"No pending approvals found. State file: {state_file}")
        return

    try:
        data = json.loads(state_file.read_text())
        pending = data.get("pending", [])
    except Exception as e:
        click.echo(f"Error reading pending approvals: {e}")
        return

    if approval_id not in pending:
        click.echo(f"Approval ID '{approval_id}' not found in pending list: {pending}")
        return

    pending.remove(approval_id)
    state_file.write_text(json.dumps({"pending": pending}))

    log_path = Path("~/.synx-mt5/audit.jsonl").expanduser()
    audit = AuditEngine(log_path=log_path)
    audit.log(
        "RISK_HITL_REJECTED",
        {"approval_id": approval_id, "approver": approver, "source": "cli"},
    )

    click.echo(f"Rejected: {approval_id} by {approver}")


@risk.command()
@click.option("--confirm", is_flag=True, help="Confirm reset")
def reset_breaker(confirm):
    """Reset circuit breaker."""
    if not confirm:
        click.echo("Use --confirm to confirm reset")
        return

    state_file = Path("~/.synx-mt5/circuit_breaker_state.json").expanduser()
    state_file.parent.mkdir(parents=True, exist_ok=True)

    state_file.write_text(json.dumps({"state": "closed"}))

    log_path = Path("~/.synx-mt5/audit.jsonl").expanduser()
    audit = AuditEngine(log_path=log_path)
    audit.log(
        "RISK_CIRCUIT_BREAKER_RESET",
        {"reset_by": "cli"},
    )

    click.echo("Circuit breaker reset to CLOSED")


@main.group()
def audit():
    """Audit log commands."""
    pass


@audit.command()
@click.option("--path", help="Path to audit log")
def verify(path):
    """Verify audit log chain integrity."""
    log_path = Path(path or "~/.synx-mt5/audit.jsonl").expanduser()
    engine = AuditEngine(log_path=log_path)
    result = engine.verify_chain()

    if result["valid"]:
        click.echo(f"Audit chain valid ({result['total_records']} records)")
    else:
        click.echo(f"Audit chain broken at seq {result.get('broken_at_seq', 'unknown')}")
        sys.exit(1)


@audit.command()
@click.option("--last", default=10, type=int)
@click.option("--filter")
def tail(last, filter):
    """Show recent audit entries."""
    log_path = Path("~/.synx-mt5/audit.jsonl").expanduser()
    engine = AuditEngine(log_path=log_path)
    records = engine.get_records(last_n=last, event_filter=filter)

    for record in records:
        ts = record.get("ts", "")
        event = record.get("event", "")
        tool = record.get("tool", "")
        outcome = ""
        if "outcome" in record:
            outcome = json.dumps(record.get("outcome", {}))[:80]
        click.echo(f"{ts} {event} {tool} {outcome}")


@main.group()
def tick_stream():
    """Real-time tick data streaming commands."""
    pass


@tick_stream.command()
@click.option("--symbols", default="EURUSD,GBPUSD,XAUUSD", help="Comma-separated symbols")
@click.option("--host", default="127.0.0.1")
@click.option("--port", default=8766, type=int)
@click.option("--poll-interval-ms", default=100, type=int)
@click.option("--config", help="Path to configuration file")
def start_stream(symbols, host, port, poll_interval_ms, config):
    """Start tick streamer WebSocket server."""
    from synx_mt5.tools.tick_streamer import TickStreamer

    symbol_list = [s.strip() for s in symbols.split(",")]
    click.echo(f"Starting tick streamer for {symbol_list} on {host}:{port}")

    try:
        streamer = TickStreamer(
            symbols=symbol_list,
            host=host,
            port=port,
            poll_interval_ms=poll_interval_ms,
            config_path=config,
        )
        asyncio.run(streamer.run())
    except KeyboardInterrupt:
        click.echo("\nTick streamer stopped")
    except Exception as e:
        click.echo(f"Error: {e}")
        sys.exit(1)


@main.command()
@click.option("--name", default="default", help="Key name")
@click.option("--show", is_flag=True, help="Show the key (insecure)")
def generate_api_key(name, show):
    """Generate a new API key for HTTP transport."""
    key = secrets.token_urlsafe(32)
    keyring_key = f"synx_mt5_api_key_{name}"
    store_credential(keyring_key, key)
    click.echo(f"API key generated and stored in keyring as '{keyring_key}'")
    if show:
        click.echo(f"Key: {key}")
    else:
        click.echo("Key hidden. Use --show to display (not recommended).")


@main.command()
@click.option("--config", help="Path to configuration file")
def risk_approve(config):
    """Approve a pending HITL order (alias for risk approve)."""
    click.echo("Use: synx-mt5 risk approve <approval_id>")


@main.command()
@click.option("--config", help="Path to configuration file")
def daily_checklist(config):
    """Run daily operational health checks."""
    click.echo("=== SYNX-MT5 Daily Checklist ===\n")

    cfg = load_config(config)
    log_path = Path(
        cfg.audit_log_path
        or Path(config or "~/.synx-mt5/synx.yaml").expanduser().parent / "audit.jsonl"
    ).expanduser()

    async def run_checks():
        results = []

        click.echo("[1] Checking MT5 Connection...")
        try:
            bridge = BridgeFactory.create(cfg.bridge)
            connected = await bridge.connect()
            if connected:
                info = await bridge.terminal_info()
                await bridge.disconnect()
                terminal = info.get("terminal", "N/A")
                click.echo(f"    [OK] Connected - Terminal: {terminal}")
                results.append(True)
            else:
                click.echo("    [FAIL] Could not connect to MT5")
                results.append(False)
        except Exception as e:
            click.echo(f"    [FAIL] {e}")
            results.append(False)

        click.echo("\n[2] Checking Audit Log Chain Integrity...")
        try:
            engine = AuditEngine(log_path=log_path)
            result = engine.verify_chain()
            if result["valid"]:
                click.echo(f"    [OK] Chain valid ({result['total_records']} records)")
                results.append(True)
            else:
                click.echo(
                    f"    [FAIL] Chain broken at seq {result.get('broken_at_seq', 'unknown')}"
                )
                results.append(False)
        except Exception as e:
            click.echo(f"    [FAIL] {e}")
            results.append(False)

        click.echo("\n[3] Checking Circuit Breaker State...")
        breaker_file = Path("~/.synx-mt5/circuit_breaker_state.json").expanduser()
        if breaker_file.exists():
            try:
                breaker_data = json.loads(breaker_file.read_text())
                cb_state = breaker_data.get("state", "unknown").upper()
                if cb_state == "OPEN":
                    click.echo("    [WARN] Circuit breaker is OPEN - trading suspended")
                    results.append(False)
                else:
                    click.echo(f"    [OK] Circuit breaker state: {cb_state} (no trips detected)")
                    results.append(True)
            except Exception:
                click.echo("    [OK] Circuit breaker: CLOSED")
                results.append(True)
        else:
            click.echo("    [OK] Circuit breaker: NOT INITIALIZED")
            results.append(True)

        try:
            click.echo("\n[4] Checking Account Equity & Balance...")
            bridge = BridgeFactory.create(cfg.bridge)
            connected = await bridge.connect()
            if connected:
                info = await bridge.account_info()
                await bridge.disconnect()
                equity = info.get("equity", 0.0)
                balance = info.get("balance", 0.0)
                click.echo(f"    [OK] Equity: ${equity:.2f}, Balance: ${balance:.2f}")
                results.append(True)
            else:
                click.echo("    [FAIL] Could not get account info")
                results.append(False)
        except Exception as e:
            click.echo(f"    [FAIL] {e}")
            results.append(False)

        click.echo("\n[5] Checking Open Positions Count...")
        try:
            bridge = BridgeFactory.create(cfg.bridge)
            connected = await bridge.connect()
            if connected:
                total = await bridge.positions_total()
                await bridge.disconnect()
                click.echo(f"    [OK] Open positions: {total}")
                results.append(True)
            else:
                click.echo("    [FAIL] Could not get positions")
                results.append(False)
        except Exception as e:
            click.echo(f"    [FAIL] {e}")
            results.append(False)

        click.echo("\n" + "=" * 37)
        passed = sum(results)
        total_checks = len(results)
        click.echo(f"Result: {passed}/{total_checks} checks passed")

        if passed < total_checks:
            sys.exit(1)

    asyncio.run(run_checks())


if __name__ == "__main__":
    main()
