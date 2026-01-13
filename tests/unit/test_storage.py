"""Unit tests for storage layer (CRUD operations)."""

from datetime import datetime

import pytest

from darwin.schemas.candidate import CandidateRecordV1, PlaybookType
from darwin.schemas.outcome_label import OutcomeLabelV1
from darwin.schemas.position import ExitReason, PositionRowV1
from darwin.storage.candidate_cache import CandidateCacheSQLite
from darwin.storage.outcome_labels import OutcomeLabelsSQLite
from darwin.storage.position_ledger import PositionLedgerSQLite


class TestCandidateCache:
    """Test CandidateCacheSQLite storage."""

    def test_put_and_get_candidate(self, candidate_cache, sample_candidate):
        """Test storing and retrieving a candidate."""
        # Store candidate
        candidate_cache.put(sample_candidate)

        # Retrieve candidate
        retrieved = candidate_cache.get(sample_candidate.candidate_id)

        assert retrieved is not None
        assert retrieved.candidate_id == sample_candidate.candidate_id
        assert retrieved.symbol == sample_candidate.symbol
        assert retrieved.playbook == sample_candidate.playbook

    def test_get_nonexistent_candidate(self, candidate_cache):
        """Test retrieving a candidate that doesn't exist."""
        retrieved = candidate_cache.get("nonexistent_id")
        assert retrieved is None

    def test_update_candidate(self, candidate_cache, sample_candidate):
        """Test updating an existing candidate."""
        # Store initial candidate
        candidate_cache.put(sample_candidate)

        # Update candidate
        sample_candidate.was_taken = False
        sample_candidate.rejection_reason = "low_confidence"
        candidate_cache.put(sample_candidate)

        # Retrieve and verify update
        retrieved = candidate_cache.get(sample_candidate.candidate_id)
        assert retrieved.was_taken is False
        assert retrieved.rejection_reason == "low_confidence"

    def test_query_by_run_id(self, candidate_cache, sample_candidate):
        """Test querying candidates by run_id."""
        # Store multiple candidates
        sample_candidate.candidate_id = "cand_001"
        candidate_cache.put(sample_candidate)

        sample_candidate.candidate_id = "cand_002"
        candidate_cache.put(sample_candidate)

        # Query by run_id
        candidates = candidate_cache.query(run_id="run_test_001")
        assert len(candidates) == 2

    def test_query_by_symbol(self, candidate_cache, sample_candidate):
        """Test querying candidates by symbol."""
        # Store candidates for different symbols
        sample_candidate.candidate_id = "cand_btc"
        sample_candidate.symbol = "BTC-USD"
        candidate_cache.put(sample_candidate)

        sample_candidate.candidate_id = "cand_eth"
        sample_candidate.symbol = "ETH-USD"
        candidate_cache.put(sample_candidate)

        # Query by symbol
        btc_candidates = candidate_cache.query(symbol="BTC-USD")
        assert len(btc_candidates) == 1
        assert btc_candidates[0].symbol == "BTC-USD"

    def test_query_by_playbook(self, candidate_cache, sample_candidate):
        """Test querying candidates by playbook."""
        # Store candidates for different playbooks
        sample_candidate.candidate_id = "cand_breakout"
        sample_candidate.playbook = PlaybookType.BREAKOUT
        candidate_cache.put(sample_candidate)

        sample_candidate.candidate_id = "cand_pullback"
        sample_candidate.playbook = PlaybookType.PULLBACK
        candidate_cache.put(sample_candidate)

        # Query by playbook
        breakout_candidates = candidate_cache.query(playbook="breakout")
        assert len(breakout_candidates) == 1
        assert breakout_candidates[0].playbook == PlaybookType.BREAKOUT

    def test_query_taken_only(self, candidate_cache, sample_candidate):
        """Test querying only taken candidates."""
        # Store taken and skipped candidates
        sample_candidate.candidate_id = "cand_taken"
        sample_candidate.was_taken = True
        candidate_cache.put(sample_candidate)

        sample_candidate.candidate_id = "cand_skipped"
        sample_candidate.was_taken = False
        candidate_cache.put(sample_candidate)

        # Query taken only
        taken_candidates = candidate_cache.query(taken_only=True)
        assert len(taken_candidates) == 1
        assert taken_candidates[0].was_taken is True

    def test_features_serialization(self, candidate_cache, sample_candidate):
        """Test that features are properly serialized and deserialized."""
        candidate_cache.put(sample_candidate)
        retrieved = candidate_cache.get(sample_candidate.candidate_id)

        assert retrieved.features == sample_candidate.features
        assert isinstance(retrieved.features, dict)

    def test_exit_spec_serialization(self, candidate_cache, sample_candidate):
        """Test that exit spec is properly serialized and deserialized."""
        candidate_cache.put(sample_candidate)
        retrieved = candidate_cache.get(sample_candidate.candidate_id)

        assert retrieved.exit_spec.stop_loss_price == sample_candidate.exit_spec.stop_loss_price
        assert retrieved.exit_spec.take_profit_price == sample_candidate.exit_spec.take_profit_price


class TestPositionLedger:
    """Test PositionLedgerSQLite storage."""

    def test_open_position(self, position_ledger, sample_position):
        """Test opening a position."""
        position_ledger.open_position(sample_position)

        # Retrieve position
        retrieved = position_ledger.get(sample_position.position_id)
        assert retrieved is not None
        assert retrieved.position_id == sample_position.position_id
        assert retrieved.is_open is True

    def test_close_position(self, position_ledger, sample_position):
        """Test closing a position."""
        # Open position
        position_ledger.open_position(sample_position)

        # Close position
        exit_info = {
            "exit_timestamp": datetime(2024, 1, 1, 13, 0),
            "exit_bar_index": 410,
            "exit_price": 51000.0,
            "exit_fees_usd": 6.25,
            "exit_reason": ExitReason.TAKE_PROFIT,
            "pnl_usd": 987.5,
            "pnl_pct": 9.875,
            "r_multiple": 2.0,
        }
        position_ledger.close_position(sample_position.position_id, exit_info)

        # Retrieve and verify
        retrieved = position_ledger.get(sample_position.position_id)
        assert retrieved.is_open is False
        assert retrieved.exit_reason == ExitReason.TAKE_PROFIT
        assert retrieved.pnl_usd == 987.5

    def test_update_position(self, position_ledger, sample_position):
        """Test updating position tracking fields."""
        # Open position
        position_ledger.open_position(sample_position)

        # Update highest price
        updates = {"highest_price": 51500.0, "trailing_activated": True}
        position_ledger.update_position(sample_position.position_id, updates)

        # Retrieve and verify
        retrieved = position_ledger.get(sample_position.position_id)
        assert retrieved.highest_price == 51500.0
        assert retrieved.trailing_activated is True

    def test_get_open_positions(self, position_ledger, sample_position):
        """Test retrieving all open positions."""
        # Open multiple positions
        sample_position.position_id = "pos_001"
        position_ledger.open_position(sample_position)

        sample_position.position_id = "pos_002"
        position_ledger.open_position(sample_position)

        # Close one position
        exit_info = {
            "exit_timestamp": datetime(2024, 1, 1, 13, 0),
            "exit_bar_index": 410,
            "exit_price": 51000.0,
            "exit_fees_usd": 6.25,
            "exit_reason": ExitReason.TAKE_PROFIT,
            "pnl_usd": 987.5,
            "pnl_pct": 9.875,
            "r_multiple": 2.0,
        }
        position_ledger.close_position("pos_002", exit_info)

        # Get open positions
        open_positions = position_ledger.get_open_positions()
        assert len(open_positions) == 1
        assert open_positions[0].position_id == "pos_001"

    def test_get_all_positions(self, position_ledger, sample_position):
        """Test retrieving all positions for a run."""
        # Open multiple positions
        sample_position.position_id = "pos_001"
        position_ledger.open_position(sample_position)

        sample_position.position_id = "pos_002"
        position_ledger.open_position(sample_position)

        # Get all positions
        all_positions = position_ledger.get_all(run_id="run_test_001")
        assert len(all_positions) == 2

    def test_get_closed_positions(self, position_ledger, sample_position):
        """Test retrieving only closed positions."""
        # Open and close a position
        position_ledger.open_position(sample_position)

        exit_info = {
            "exit_timestamp": datetime(2024, 1, 1, 13, 0),
            "exit_bar_index": 410,
            "exit_price": 51000.0,
            "exit_fees_usd": 6.25,
            "exit_reason": ExitReason.TAKE_PROFIT,
            "pnl_usd": 987.5,
            "pnl_pct": 9.875,
            "r_multiple": 2.0,
        }
        position_ledger.close_position(sample_position.position_id, exit_info)

        # Get closed positions
        closed_positions = position_ledger.get_all(run_id="run_test_001", closed_only=True)
        assert len(closed_positions) == 1
        assert closed_positions[0].is_open is False

    def test_position_not_found(self, position_ledger):
        """Test retrieving non-existent position."""
        retrieved = position_ledger.get("nonexistent_id")
        assert retrieved is None

    def test_pnl_calculations(self, position_ledger, sample_position):
        """Test that PnL is correctly stored."""
        position_ledger.open_position(sample_position)

        # Close with profit
        exit_info = {
            "exit_timestamp": datetime(2024, 1, 1, 13, 0),
            "exit_bar_index": 410,
            "exit_price": 52000.0,  # +$2000 on $1000 position
            "exit_fees_usd": 12.5,  # Total fees (entry + exit)
            "exit_reason": ExitReason.TAKE_PROFIT,
            "pnl_usd": 1987.5,  # $2000 - $12.5
            "pnl_pct": 198.75,  # ~199%
            "r_multiple": 2.0,
        }
        position_ledger.close_position(sample_position.position_id, exit_info)

        retrieved = position_ledger.get(sample_position.position_id)
        assert retrieved.pnl_usd == 1987.5
        assert retrieved.r_multiple == 2.0


class TestOutcomeLabels:
    """Test OutcomeLabelsSQLite storage."""

    def test_upsert_label(self, temp_db_path):
        """Test inserting and updating outcome labels."""
        labels_store = OutcomeLabelsSQLite(temp_db_path)

        label = OutcomeLabelV1(
            candidate_id="cand_001",
            run_id="run_test_001",
            label_timestamp=datetime(2024, 1, 1, 13, 0),
            was_taken=True,
            best_r_at_tp=2.5,
            best_r_at_sl=-0.8,
            best_r_at_time=1.8,
            worst_r_at_tp=0.5,
            worst_r_at_sl=-1.0,
            worst_r_at_time=-0.2,
            actual_r=1.8,
            actual_exit_reason="take_profit",
        )

        # Insert label
        labels_store.upsert_label(label)

        # Retrieve label
        retrieved = labels_store.get(label.candidate_id)
        assert retrieved is not None
        assert retrieved.candidate_id == label.candidate_id
        assert retrieved.best_r_at_tp == label.best_r_at_tp

        # Update label
        label.actual_r = 2.0
        labels_store.upsert_label(label)

        # Verify update
        retrieved = labels_store.get(label.candidate_id)
        assert retrieved.actual_r == 2.0

        labels_store.close()

    def test_query_labels_by_run(self, temp_db_path):
        """Test querying labels by run_id."""
        labels_store = OutcomeLabelsSQLite(temp_db_path)

        # Insert multiple labels
        for i in range(3):
            label = OutcomeLabelV1(
                candidate_id=f"cand_{i:03d}",
                run_id="run_test_001",
                label_timestamp=datetime(2024, 1, 1, 13, 0),
                was_taken=True,
                best_r_at_tp=2.5,
                best_r_at_sl=-0.8,
                best_r_at_time=1.8,
                worst_r_at_tp=0.5,
                worst_r_at_sl=-1.0,
                worst_r_at_time=-0.2,
                actual_r=1.8,
                actual_exit_reason="take_profit",
            )
            labels_store.upsert_label(label)

        # Query labels
        labels = labels_store.query(run_id="run_test_001")
        assert len(labels) == 3

        labels_store.close()

    def test_get_nonexistent_label(self, temp_db_path):
        """Test retrieving a label that doesn't exist."""
        labels_store = OutcomeLabelsSQLite(temp_db_path)
        retrieved = labels_store.get("nonexistent_id")
        assert retrieved is None
        labels_store.close()


class TestStorageIntegrity:
    """Test storage layer integrity and edge cases."""

    def test_concurrent_candidate_inserts(self, candidate_cache, sample_candidate):
        """Test multiple rapid inserts."""
        for i in range(10):
            sample_candidate.candidate_id = f"cand_{i:03d}"
            candidate_cache.put(sample_candidate)

        candidates = candidate_cache.query(run_id="run_test_001")
        assert len(candidates) == 10

    def test_large_features_dict(self, candidate_cache, sample_candidate):
        """Test storing candidate with large features dictionary."""
        # Add many features
        large_features = {f"feature_{i}": float(i) for i in range(100)}
        sample_candidate.features = large_features

        candidate_cache.put(sample_candidate)
        retrieved = candidate_cache.get(sample_candidate.candidate_id)

        assert len(retrieved.features) == 100
        assert retrieved.features["feature_50"] == 50.0

    def test_null_optional_fields(self, candidate_cache, sample_candidate):
        """Test storing candidate with null optional fields."""
        sample_candidate.llm_decision = None
        sample_candidate.llm_confidence = None
        sample_candidate.payload_ref = None
        sample_candidate.position_id = None

        candidate_cache.put(sample_candidate)
        retrieved = candidate_cache.get(sample_candidate.candidate_id)

        assert retrieved.llm_decision is None
        assert retrieved.llm_confidence is None

    def test_position_tracking_updates(self, position_ledger, sample_position):
        """Test multiple updates to position tracking fields."""
        position_ledger.open_position(sample_position)

        # Simulate position tracking over time
        updates_sequence = [
            {"highest_price": 50500.0},
            {"highest_price": 51000.0, "trailing_activated": True},
            {"highest_price": 51500.0},
        ]

        for updates in updates_sequence:
            position_ledger.update_position(sample_position.position_id, updates)

        retrieved = position_ledger.get(sample_position.position_id)
        assert retrieved.highest_price == 51500.0
        assert retrieved.trailing_activated is True
