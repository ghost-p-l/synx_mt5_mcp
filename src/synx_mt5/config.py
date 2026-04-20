"""Configuration schema and loader for SYNX-MT5-MCP"""

from pathlib import Path

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, Field


class ServerConfig(BaseModel):
    """Server configuration."""

    name: str = "synx_mt5_mcp"
    version: str = "1.1.0"
    log_level: str = "INFO"
    log_format: str = "json"
    storage_path: Path = Path("~/.synx-mt5").expanduser()


class TransportConfig(BaseModel):
    """Transport layer configuration."""

    mode: str = "stdio"
    http_host: str = "127.0.0.1"
    http_port: int = 8765
    api_key_required: bool = True


class BridgeConfig(BaseModel):
    """MT5 bridge configuration."""

    mode: str = "python_com"
    terminal_path: str | None = None
    reconnect_interval_seconds: int = 30
    max_retries: int = 5
    backoff_factor: float = 2.0
    ea_host: str = "127.0.0.1"
    ea_port: int = 18765
    ea_timeout_seconds: int = 5
    ea_api_key: str | None = None
    ea_files_dir: str | None = None  # Override for SYNX_EA file IPC path (auto-detected if None)
    metaeditor_path: str | None = None
    filling_mode: str = "ioc"
    slippage_points: int = 20


class ProfileConfig(BaseModel):
    """Capability profile configuration."""

    name: str = "analyst"
    allowed_tools: list[str] = Field(default_factory=list)
    hitl_required: list[str] = Field(default_factory=list)
    rate_limits: dict = Field(default_factory=dict)


class RiskConfig(BaseModel):
    """Risk management configuration."""

    require_sl: bool = True
    min_sl_pips: int = 8  # Professional: 8-10 pips minimum
    min_rr_ratio: float = 1.0  # Professional: 1:1 minimum
    max_risk_per_trade_pct: float = 0.5  # Professional: 0.5% max per trade
    max_total_exposure_pct: float = 30.0
    max_positions_per_symbol: int = 5
    max_total_positions: int = 20
    max_session_drawdown_pct: float = 5.0  # Professional: 5% session limit
    max_daily_drawdown_pct: float = 10.0  # Professional: 10% daily max
    cooldown_seconds: int = 60  # Professional: wait between trades


class HITLConfig(BaseModel):
    """Human-in-the-loop configuration."""

    enabled: bool = False
    tools: list[str] = Field(default_factory=list)
    timeout_seconds: int = 30
    sink: str = "terminal"
    webhook_url: str | None = None
    webhook_secret: str | None = None
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None


class IdempotencyConfig(BaseModel):
    """Idempotency engine configuration."""

    ttl_seconds: int = 5  # Fast for scalping
    max_cache_size: int = 500


class SecurityConfig(BaseModel):
    """Security layer configuration."""

    prompt_injection_shield: bool = True
    audit_log_enabled: bool = True
    audit_log_path: Path = Path("~/.synx-mt5/audit.jsonl").expanduser()
    chain_verification: bool = True
    rotate_size_mb: int = 100


class RegimeDetectorConfig(BaseModel):
    """Market regime detector configuration."""

    adx_threshold: float = 25.0
    volatility_high: float = 0.005
    volatility_low: float = 0.001


class CorrelationConfig(BaseModel):
    """Correlation tracker configuration."""

    high_threshold: float = 0.75


class IntelligenceConfig(BaseModel):
    """Intelligence layer configuration."""

    cache_ttl_seconds: int = 300
    regime_detector: RegimeDetectorConfig = Field(default_factory=RegimeDetectorConfig)
    correlation: CorrelationConfig = Field(default_factory=CorrelationConfig)


class MQL5Config(BaseModel):
    """MQL5 development configuration."""

    metaeditor_path: str | None = None
    mql5_dir: str | None = None
    max_file_size_kb: int = 512
    compile_timeout_seconds: int = 60


class StrategyTesterConfig(BaseModel):
    """Strategy tester configuration."""

    results_dir: str | None = None
    max_concurrent_tests: int = 1


class Config(BaseModel):
    """Main configuration container."""

    server: ServerConfig = Field(default_factory=ServerConfig)
    transport: TransportConfig = Field(default_factory=TransportConfig)
    bridge: BridgeConfig = Field(default_factory=BridgeConfig)
    profile: str = "analyst"
    risk: RiskConfig = Field(default_factory=RiskConfig)
    hitl: HITLConfig = Field(default_factory=HITLConfig)
    idempotency: IdempotencyConfig = Field(default_factory=IdempotencyConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    intelligence: IntelligenceConfig = Field(default_factory=IntelligenceConfig)
    mql5_dev: MQL5Config = Field(default_factory=MQL5Config)
    strategy_tester: StrategyTesterConfig = Field(default_factory=StrategyTesterConfig)

    @classmethod
    def from_yaml(cls, path: Path) -> "Config":
        """Load configuration from YAML file."""
        if not path.exists():
            return cls()
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return cls(**data)

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        return cls()


def load_config(config_path: str | None = None) -> Config:
    """Load configuration from file or environment."""
    if config_path:
        return Config.from_yaml(Path(config_path))
    default = Path("~/.synx-mt5/synx.yaml").expanduser()
    if default.exists():
        return Config.from_yaml(default)
    return Config.from_env()
