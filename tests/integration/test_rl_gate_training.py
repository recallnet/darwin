"""Integration test for gate agent training end-to-end."""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from darwin.rl.training.offline_batch import OfflineBatchTrainer, train_gate_agent
from darwin.rl.envs.gate_env import ReplayGateEnv
from darwin.schemas.candidate import CandidateRecordV1, ExitSpecV1, PlaybookType
from darwin.schemas.outcome_label import OutcomeLabelV1
from darwin.storage.candidate_cache import CandidateCacheSQLite
from darwin.storage.outcome_labels import OutcomeLabelsSQLite


class TestGateAgentTrainingEndToEnd:
    """Test end-to-end gate agent training workflow."""

    def create_mock_training_data(
        self,
        candidate_cache_path: str,
        outcome_labels_path: str,
        num_samples: int = 150,
    ) -> None:
        """Create mock training data.

        Args:
            candidate_cache_path: Path to candidate cache
            outcome_labels_path: Path to outcome labels
            num_samples: Number of samples to create
        """
        candidate_cache = CandidateCacheSQLite(candidate_cache_path)
        outcome_labels = OutcomeLabelsSQLite(outcome_labels_path)

        run_id = "test_run_001"

        for i in range(num_samples):
            # Create candidate
            candidate = CandidateRecordV1(
                candidate_id=f"cand_{i:04d}",
                run_id=run_id,
                timestamp=datetime.now(),
                symbol="BTC-USD",
                timeframe="15m",
                bar_index=100 + i,
                playbook=PlaybookType.BREAKOUT if i % 2 == 0 else PlaybookType.PULLBACK,
                direction="long" if i % 3 == 0 else "short",
                entry_price=45000.0 + (i * 10),
                atr_at_entry=500.0,
                exit_spec=ExitSpecV1(
                    stop_loss_price=44500.0 + (i * 10),
                    take_profit_price=46000.0 + (i * 10),
                    time_stop_bars=32,
                    trailing_enabled=True,
                ),
                features={
                    "close": 45000.0 + (i * 10),
                    "atr_bps": 100.0,
                    "rsi14": 50.0 + (i % 20),
                    "adx14": 20.0 + (i % 10),
                    "open_positions": i % 3,
                    "exposure_frac": (i % 5) / 10.0,
                    "dd_24h_bps": -(i % 30),
                    "halt_flag": 0,
                },
                was_taken=False,
                llm_decision="skip",
            )

            candidate_cache.put(candidate)

            # Create outcome label
            # 60% winners, 40% losers
            r_multiple = 1.5 if i % 5 < 3 else -0.5

            outcome = OutcomeLabelV1(
                label_id=f"label_{i:04d}",
                candidate_id=f"cand_{i:04d}",
                created_at=datetime.now(),
                was_taken=False,
                counterfactual_r_multiple=r_multiple,
            )

            outcome_labels.upsert_label(outcome)

        candidate_cache.close()
        outcome_labels.close()

    def test_gate_agent_training_workflow(self):
        """Test complete gate agent training workflow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create paths
            candidate_cache_path = str(tmpdir_path / "candidate_cache.sqlite")
            outcome_labels_path = str(tmpdir_path / "outcome_labels.sqlite")
            model_output_path = str(tmpdir_path / "gate_model")

            # Create mock training data
            self.create_mock_training_data(
                candidate_cache_path=candidate_cache_path,
                outcome_labels_path=outcome_labels_path,
                num_samples=150,
            )

            # Initialize storage
            candidate_cache = CandidateCacheSQLite(candidate_cache_path)
            outcome_labels = OutcomeLabelsSQLite(outcome_labels_path)

            # Initialize trainer
            trainer = OfflineBatchTrainer(
                agent_name="gate",
                env_class=ReplayGateEnv,
                candidate_cache=candidate_cache,
                outcome_labels=outcome_labels,
            )

            # Prepare data
            train_episodes, val_episodes = trainer.prepare_episodes(
                run_ids=["test_run_001"],
                train_split=0.8,
                min_samples=100,
            )

            # Verify data preparation
            assert len(train_episodes) == 120  # 80% of 150
            assert len(val_episodes) == 30  # 20% of 150

            # Verify episode structure
            assert "candidate" in train_episodes[0]
            assert "outcome" in train_episodes[0]
            assert "portfolio_state" in train_episodes[0]

            # Train model (small number of timesteps for testing)
            model = trainer.train(
                train_episodes=train_episodes,
                val_episodes=val_episodes,
                total_timesteps=500,  # Small for fast test
                verbose=0,  # Suppress output
            )

            # Verify model was created
            assert model is not None

            # Evaluate model
            val_metrics = trainer.evaluate(model, val_episodes)

            # Verify evaluation metrics
            assert "mean_reward" in val_metrics
            assert "std_reward" in val_metrics
            assert "n_episodes" in val_metrics
            assert val_metrics["n_episodes"] == 30

            # Save model
            model.save(model_output_path)

            # Verify model was saved
            assert Path(f"{model_output_path}.zip").exists()

            # Close storage
            candidate_cache.close()
            outcome_labels.close()

    def test_train_gate_agent_convenience_function(self):
        """Test train_gate_agent convenience function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create paths
            candidate_cache_path = str(tmpdir_path / "candidate_cache.sqlite")
            outcome_labels_path = str(tmpdir_path / "outcome_labels.sqlite")
            model_output_path = str(tmpdir_path / "gate_model")

            # Create mock training data
            self.create_mock_training_data(
                candidate_cache_path=candidate_cache_path,
                outcome_labels_path=outcome_labels_path,
                num_samples=150,
            )

            # Train using convenience function
            model, val_metrics = train_gate_agent(
                run_ids=["test_run_001"],
                candidate_cache_path=candidate_cache_path,
                outcome_labels_path=outcome_labels_path,
                output_model_path=model_output_path,
                total_timesteps=500,  # Small for fast test
            )

            # Verify model was trained
            assert model is not None

            # Verify validation metrics
            assert "mean_reward" in val_metrics
            assert "n_episodes" in val_metrics

            # Verify model was saved
            assert Path(f"{model_output_path}.zip").exists()

    def test_insufficient_training_samples(self):
        """Test error handling with insufficient samples."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create paths
            candidate_cache_path = str(tmpdir_path / "candidate_cache.sqlite")
            outcome_labels_path = str(tmpdir_path / "outcome_labels.sqlite")

            # Create small amount of data
            self.create_mock_training_data(
                candidate_cache_path=candidate_cache_path,
                outcome_labels_path=outcome_labels_path,
                num_samples=50,  # Below minimum
            )

            # Initialize storage
            candidate_cache = CandidateCacheSQLite(candidate_cache_path)
            outcome_labels = OutcomeLabelsSQLite(outcome_labels_path)

            # Initialize trainer
            trainer = OfflineBatchTrainer(
                agent_name="gate",
                env_class=ReplayGateEnv,
                candidate_cache=candidate_cache,
                outcome_labels=outcome_labels,
            )

            # Should raise error for insufficient samples
            with pytest.raises(ValueError, match="Insufficient samples"):
                trainer.prepare_episodes(
                    run_ids=["test_run_001"],
                    train_split=0.8,
                    min_samples=100,
                )

            # Close storage
            candidate_cache.close()
            outcome_labels.close()
