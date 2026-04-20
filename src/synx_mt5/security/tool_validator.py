"""Tool poisoning defenses - Tool metadata integrity verification."""

import hashlib
import json

import structlog

log = structlog.get_logger(__name__)


class ToolSchemaIntegrity:
    """
    Verifies tool schema integrity on startup.
    Detects any runtime modification of tool metadata.
    """

    def __init__(self):
        self._schema_hash: str = ""
        self._verified: bool = False

    def compute_hash(self, tools: list[dict]) -> str:
        """Compute SHA-256 hash of tool schemas."""
        schemas = []
        for tool in tools:
            schema = {
                "name": tool.get("name"),
                "description": tool.get("description"),
                "inputSchema": tool.get("inputSchema"),
            }
            schemas.append(schema)

        content = json.dumps(schemas, sort_keys=True)
        return f"sha256:{hashlib.sha256(content.encode()).hexdigest()}"

    def verify(self, tools: list[dict]) -> bool:
        """Verify tool schemas match startup hash."""
        current_hash = self.compute_hash(tools)

        if not self._schema_hash:
            self._schema_hash = current_hash
            self._verified = True
            log.info("tool_schema_hash_computed", hash=self._schema_hash)
            return True

        if current_hash != self._schema_hash:
            log.error(
                "tool_schema_integrity_violation", expected=self._schema_hash, actual=current_hash
            )
            return False

        return True

    @property
    def hash(self) -> str:
        return self._schema_hash


class ToolValidator:
    """
    Validates tool input against schema.
    Prevents malformed tool calls.
    """

    def validate_input(self, tool_name: str, params: dict, schema: dict) -> tuple[bool, str]:
        """
        Validate tool input parameters.

        Returns:
            (is_valid, error_message)
        """
        input_schema = schema.get("inputSchema", {})
        properties = input_schema.get("properties", {})
        required = input_schema.get("required", [])

        for req_field in required:
            if req_field not in params:
                return False, f"Missing required field: {req_field}"

        for field, value in params.items():
            if field not in properties:
                continue

            expected_type = properties[field].get("type")
            if expected_type == "string" and not isinstance(value, str):
                return False, f"Field '{field}' must be string"
            elif expected_type == "number" and not isinstance(value, (int, float)):
                return False, f"Field '{field}' must be number"
            elif expected_type == "boolean" and not isinstance(value, bool):
                return False, f"Field '{field}' must be boolean"
            elif expected_type == "array" and not isinstance(value, list):
                return False, f"Field '{field}' must be array"

        return True, ""
