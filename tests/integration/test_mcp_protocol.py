"""Integration tests for MCP protocol compliance."""

import re


class TestMCPProtocolCompliance:
    """Test MCP protocol compliance for tool registration."""

    def test_tool_schemas_are_static(self):
        """Tool schemas must be static, not from config."""
        from synx_mt5.tools.registry import TOOL_SCHEMAS

        for _tool_name, schema in TOOL_SCHEMAS.items():
            assert isinstance(schema, dict)
            assert "description" in schema
            assert isinstance(schema["description"], str)
            assert len(schema["description"]) > 10

    def test_all_registry_tools_have_schemas(self):
        """Every registered tool must have a schema."""
        from synx_mt5.tools.registry import TOOL_SCHEMAS

        assert len(TOOL_SCHEMAS) >= 50, f"Expected 50+ tools, got {len(TOOL_SCHEMAS)}"
        for tool_name, schema in TOOL_SCHEMAS.items():
            assert "inputSchema" in schema, f"{tool_name} missing inputSchema"
            assert schema["inputSchema"].get("type") == "object", (
                f"{tool_name} inputSchema must be object"
            )

    def test_all_tools_have_descriptions(self):
        """Every tool must have a non-empty description."""
        from synx_mt5.tools.registry import TOOL_SCHEMAS

        for tool_name, schema in TOOL_SCHEMAS.items():
            desc = schema.get("description", "")
            assert len(desc) > 10, f"{tool_name} has no description"
            assert "{placeholder}" not in desc
            assert "{TODO}" not in desc


class TestMCPToolNamingConventions:
    """Test that tools follow MCP naming conventions."""

    def test_tools_use_snake_case(self):
        """Tool names must use snake_case."""
        from synx_mt5.tools.registry import TOOL_SCHEMAS

        for tool_name in TOOL_SCHEMAS:
            assert re.match(r"^[a-z][a-z0-9_]*$", tool_name), (
                f"Tool '{tool_name}' must use snake_case"
            )

    def test_tool_names_are_lowercase(self):
        """Tool names must be lowercase."""
        from synx_mt5.tools.registry import TOOL_SCHEMAS

        for tool_name in TOOL_SCHEMAS:
            assert tool_name == tool_name.lower(), f"Tool '{tool_name}' must be lowercase"

    def test_tool_names_no_leading_underscore(self):
        """Tool names must not start with underscore (not internal tools)."""
        from synx_mt5.tools.registry import TOOL_SCHEMAS

        for tool_name in TOOL_SCHEMAS:
            assert not tool_name.startswith("_"), f"Tool '{tool_name}' starts with underscore"


class TestMCPResourceCompliance:
    """Test MCP resource endpoint compliance."""

    def test_guide_functions_exist(self):
        """All guide functions must exist and return content."""
        from synx_mt5.resources import guides

        guide_funcs = [
            guides.get_getting_started,
            guides.get_security_model,
            guides.get_trading_guide,
            guides.get_market_data_guide,
            guides.get_intelligence_guide,
            guides.get_chart_control_guide,
            guides.get_mql5_dev_guide,
        ]

        for func in guide_funcs:
            content = func()
            assert isinstance(content, str), f"{func.__name__} must return str"
            assert len(content) > 100, f"{func.__name__} content too short"

    def test_guide_functions_return_mt5_content(self):
        """Guide content should reference MT5 topics."""
        from synx_mt5.resources import guides

        content = guides.get_getting_started()
        assert "MT5" in content or "MetaTrader" in content

    def test_active_profile_content_dynamic(self):
        """Profile content must be dynamically generated."""
        from synx_mt5.resources.guides import get_active_profile_content

        content = get_active_profile_content("analyst", ["initialize", "account_info"])
        assert isinstance(content, str)
        assert len(content) > 50

    def test_risk_limits_content_dynamic(self):
        """Risk limits content must be dynamically generated."""
        from synx_mt5.resources.guides import get_risk_limits_content

        content = get_risk_limits_content({"max_drawdown_pct": 5.0})
        assert isinstance(content, str)
        assert len(content) > 50


class TestCapabilityProfileEnforcement:
    """Test that capability profiles correctly filter tools."""

    def test_read_only_profile_excludes_execution_tools(self):
        """read_only profile must not include execution tools."""
        from synx_mt5.security.capability import get_active_profile, load_profile, reset_profile

        reset_profile()
        load_profile(
            "read_only",
            [
                "initialize",
                "get_symbols",
                "get_symbol_info",
                "copy_rates_from_pos",
                "order_send",
                "account_info",
            ],
        )
        _, profile = get_active_profile()
        assert "order_send" not in profile
        assert "initialize" in profile

    def test_executor_profile_includes_chart_tools(self):
        """executor profile must include chart tools."""
        from synx_mt5.security.capability import get_active_profile, load_profile, reset_profile

        reset_profile()
        load_profile(
            "executor",
            [
                "initialize",
                "get_symbols",
                "order_send",
                "chart_open",
                "chart_close",
                "chart_screenshot",
            ],
        )
        _, profile = get_active_profile()
        assert "chart_open" in profile
        assert "chart_close" in profile
        assert "chart_screenshot" in profile

    def test_active_profile_loaded_with_tools(self):
        """load_profile correctly populates the active profile."""
        from synx_mt5.security.capability import get_active_profile, load_profile, reset_profile

        reset_profile()
        load_profile("analyst", ["account_info", "positions_get", "get_risk_status"])
        _, profile = get_active_profile()
        assert len(profile) == 3
        assert "account_info" in profile
        assert "positions_get" in profile


class TestMCPHandlerServices:
    """Test that HandlerServices includes all required service attributes."""

    def test_handler_services_has_all_services(self):
        """HandlerServices must have all service attributes referenced by handlers."""
        import inspect

        from synx_mt5.tools.registry import HandlerServices

        sig = inspect.signature(HandlerServices)
        attrs = list(sig.parameters.keys())
        required = [
            "connection_manager",
            "market_data_service",
            "intelligence_service",
            "position_service",
            "history_service",
            "risk_service",
            "terminal_mgmt_service",
            "market_depth_service",
            "chart_service",
            "mql5_service",
            "backtest_service",
            "execution_service",
            "bridge",
            "audit",
            "config",
        ]
        for attr in required:
            assert attr in attrs, f"HandlerServices missing '{attr}'"
