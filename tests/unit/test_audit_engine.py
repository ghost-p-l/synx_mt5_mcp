"""Unit tests for audit engine module."""

import json
import tempfile
from pathlib import Path

import pytest

from synx_mt5.audit.engine import AuditEngine, AuditEventType


class TestAuditEngine:
    """Test AuditEngine class."""

    @pytest.fixture
    def temp_log_path(self):
        """Create temporary log path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "audit.jsonl"

    @pytest.fixture
    def engine(self, temp_log_path):
        """Create audit engine with empty log."""
        return AuditEngine(log_path=temp_log_path, chain_verification=True)

    def test_init_empty_log(self, engine, temp_log_path):
        """Test init with empty log."""
        assert engine._seq == 0
        assert engine._last_hash == "genesis"
        assert temp_log_path.exists()

    def test_init_existing_log(self, temp_log_path):
        """Test init with existing log loads last hash."""
        temp_log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(temp_log_path, "w") as f:
            record = {
                "seq": 1,
                "ts": "2024-01-01T00:00:00+00:00",
                "event": "test.event",
                "session_id": "ses_test",
                "prev_hash": "genesis",
                "self_hash": "sha256:abc123",
            }
            f.write(json.dumps(record) + "\n")

        engine = AuditEngine(log_path=temp_log_path, chain_verification=True)
        assert engine._seq == 1

    def test_log_increments_seq(self, engine):
        """Test log increments sequence."""
        engine.log("test.event", {"data": "value"})
        assert engine._seq == 1
        engine.log("test.event2", {"data": "value2"})
        assert engine._seq == 2

    def test_log_computes_self_hash(self, engine):
        """Test log computes self_hash."""
        record = engine.log("test.event", {"key": "value"})
        assert "self_hash" in record
        assert record["self_hash"].startswith("sha256:")

    def test_log_links_prev_hash(self, engine):
        """Test log links to prev_hash."""
        first = engine.log("test.event1", {})
        assert first["prev_hash"] == "genesis"

        second = engine.log("test.event2", {})
        assert second["prev_hash"] == first["self_hash"]

    def test_log_returns_record(self, engine):
        """Test log returns the record."""
        record = engine.log("test.event", {"data": "value"})
        assert record["event"] == "test.event"
        assert record["data"] == "value"
        assert record["seq"] == 1


class TestAuditEngineGetRecords:
    """Test get_records method."""

    @pytest.fixture
    def temp_log_path(self):
        """Create temporary log path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "audit.jsonl"

    @pytest.fixture
    def engine_with_records(self, temp_log_path):
        """Create engine with multiple records."""
        engine = AuditEngine(log_path=temp_log_path)
        for i in range(5):
            engine.log("test.event", {"index": i})
        return engine

    def test_get_records_no_filter(self, engine_with_records):
        """Test get_records returns all records."""
        records = engine_with_records.get_records()
        assert len(records) == 5

    def test_get_records_last_n(self, engine_with_records):
        """Test get_records with last_n."""
        records = engine_with_records.get_records(last_n=2)
        assert len(records) == 2
        assert records[-1]["seq"] == 5

    def test_get_records_event_filter(self, engine_with_records):
        """Test get_records with event_filter."""
        records = engine_with_records.get_records(event_filter="test.event")
        assert len(records) == 5

    def test_get_records_no_match(self, engine_with_records):
        """Test get_records returns empty when no match."""
        records = engine_with_records.get_records(event_filter="nonexistent")
        assert len(records) == 0


class TestAuditEngineVerifyChain:
    """Test verify_chain method."""

    @pytest.fixture
    def temp_log_path(self):
        """Create temporary log path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "audit.jsonl"

    def test_verify_chain_empty_log(self, temp_log_path):
        """Test verify_chain with empty log."""
        engine = AuditEngine(log_path=temp_log_path)
        result = engine.verify_chain()
        assert result["valid"] is True
        assert result["total_records"] == 0

    def test_verify_chain_valid_chain(self, temp_log_path):
        """Test verify_chain with valid chain."""
        engine = AuditEngine(log_path=temp_log_path)
        for i in range(3):
            engine.log("test.event", {"index": i})

        result = engine.verify_chain()
        assert result["valid"] is True
        assert result["total_records"] == 3

    def test_verify_chain_tampered_hash(self, temp_log_path):
        """Test verify_chain detects tampered self_hash."""
        engine = AuditEngine(log_path=temp_log_path)
        engine.log("test.event", {"data": "original"})

        with open(temp_log_path) as f:
            lines = f.readlines()

        record = json.loads(lines[0])
        record["data"] = "tampered"

        with open(temp_log_path, "w") as f:
            f.write(json.dumps(record) + "\n")

        result = engine.verify_chain()
        assert result["valid"] is False
        assert result["broken_at_seq"] == 1

    def test_verify_chain_broken_prev_hash(self, temp_log_path):
        """Test verify_chain detects broken prev_hash chain."""
        engine = AuditEngine(log_path=temp_log_path)
        engine.log("test.event1", {})
        engine.log("test.event2", {})

        with open(temp_log_path) as f:
            lines = f.readlines()

        second_record = json.loads(lines[1])
        second_record["prev_hash"] = "wrong_hash"

        lines[1] = json.dumps(second_record) + "\n"
        with open(temp_log_path, "w") as f:
            f.writelines(lines)

        result = engine.verify_chain()
        assert result["valid"] is False
        assert result["broken_at_seq"] == 2


class TestAuditEngineSessionId:
    """Test session_id property."""

    @pytest.fixture
    def temp_log_path(self):
        """Create temporary log path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "audit.jsonl"

    def test_session_id_format(self, temp_log_path):
        """Test session_id has expected format."""
        engine = AuditEngine(log_path=temp_log_path)
        assert engine.session_id.startswith("ses_")
        assert len(engine.session_id) > 6

    def test_session_id_unique(self, temp_log_path):
        """Test session_id is unique per instance."""
        engine1 = AuditEngine(log_path=temp_log_path)
        engine2 = AuditEngine(log_path=temp_log_path)
        assert engine1.session_id != engine2.session_id


class TestAuditEngineLogRotation:
    """Test log rotation."""

    @pytest.fixture
    def temp_log_path(self):
        """Create temporary log path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "audit.jsonl"

    def test_log_rotation_size_limit(self, temp_log_path):
        """Test log rotation at size limit."""
        engine = AuditEngine(log_path=temp_log_path, rotate_size_mb=0.0001)
        for _ in range(100):
            engine.log("test.event", {"data": "x" * 1000})

        records = engine.get_records()
        assert len(records) <= 10

    def test_log_rotation_creates_new_log(self, temp_log_path):
        """Test rotation creates new log file."""
        engine = AuditEngine(log_path=temp_log_path, rotate_size_mb=0.0001)
        for _ in range(5):
            engine.log("test.event", {"data": "x" * 500})

        rotated_files = list(temp_log_path.parent.glob("*.jsonl"))
        assert len(rotated_files) > 1


class TestAuditEventType:
    """Test AuditEventType constants."""

    def test_event_types_exist(self):
        """Test required event types exist."""
        assert hasattr(AuditEventType, "SERVER_START")
        assert hasattr(AuditEventType, "RISK_CIRCUIT_BREAKER_OPEN")
        assert hasattr(AuditEventType, "RISK_HITL_REQUIRED")
        assert hasattr(AuditEventType, "RISK_HITL_APPROVED")
        assert hasattr(AuditEventType, "RISK_HITL_REJECTED")

    def test_all_event_types_string(self):
        """Test all event types are strings."""
        from synx_mt5.audit.engine import ALL_EVENT_TYPES

        for event in ALL_EVENT_TYPES:
            assert isinstance(event, str)
            assert "." in event
