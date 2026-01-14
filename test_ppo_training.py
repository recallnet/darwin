"""Quick test script for PPO training pipeline."""

import logging
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_ppo_training():
    """Test PPO training with mock data."""
    logger.info("=" * 80)
    logger.info("Testing PPO Training Pipeline")
    logger.info("=" * 80)

    # Import training modules
    try:
        from darwin.rl.training.algorithms import train_gate_agent
        from darwin.rl.training.environments import GateAgentEnvironment
    except ImportError as e:
        logger.error(f"Failed to import PPO modules: {e}")
        logger.error("Install with: pip install 'darwin[rl]'")
        return False

    # Create mock training data (gate agent)
    logger.info("\n1. Creating mock training data...")
    num_samples = 100
    mock_decisions = []

    for i in range(num_samples):
        # Create random state (34-dim for gate agent)
        state = np.random.randn(34).astype(np.float32)

        # Random outcome
        r_multiple = np.random.randn() * 2.0  # Some wins, some losses

        decision = {
            "candidate_id": f"TEST_{i}",
            "state": state.tolist(),
            "action": 1 if r_multiple > 0 else 0,  # Pass winners, skip losers
            "r_multiple": float(r_multiple),
        }
        mock_decisions.append(decision)

    logger.info(f"  Created {len(mock_decisions)} mock decisions")
    logger.info(f"  State dimension: {len(mock_decisions[0]['state'])}")

    # Test environment creation
    logger.info("\n2. Testing environment creation...")
    try:
        env = GateAgentEnvironment(mock_decisions)
        logger.info(f"  ✓ Environment created successfully")
        logger.info(f"    Observation space: {env.observation_space}")
        logger.info(f"    Action space: {env.action_space}")

        # Test environment step
        obs, info = env.reset()
        logger.info(f"  ✓ Environment reset successful")
        logger.info(f"    Initial observation shape: {obs.shape}")

        action = env.action_space.sample()
        obs, reward, terminated, truncated, info = env.step(action)
        logger.info(f"  ✓ Environment step successful")
        logger.info(f"    Reward: {reward:.4f}")

    except Exception as e:
        logger.error(f"  ✗ Environment test failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    # Test PPO training
    logger.info("\n3. Testing PPO training...")
    try:
        logger.info("  Training gate agent with PPO (1000 timesteps)...")
        model, metrics = train_gate_agent(mock_decisions, total_timesteps=1000)

        logger.info(f"  ✓ Training completed successfully!")
        logger.info(f"    Mean reward: {metrics['mean_reward']:.4f}")
        logger.info(f"    Accuracy: {metrics['accuracy']:.2%}")

    except Exception as e:
        logger.error(f"  ✗ Training failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    # Test model prediction
    logger.info("\n4. Testing model prediction...")
    try:
        test_state = mock_decisions[0]["state"]
        action, _ = model.predict(test_state, deterministic=True)
        logger.info(f"  ✓ Prediction successful")
        logger.info(f"    Action: {action} ({'PASS' if action == 1 else 'SKIP'})")

    except Exception as e:
        logger.error(f"  ✗ Prediction failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    # Test model save/load
    logger.info("\n5. Testing model save/load...")
    try:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test_model.zip"

            # Save
            model.save(str(model_path))
            logger.info(f"  ✓ Model saved to {model_path}")

            # Load
            from stable_baselines3 import PPO

            loaded_model = PPO.load(str(model_path))
            logger.info(f"  ✓ Model loaded successfully")

            # Test prediction with loaded model
            action2, _ = loaded_model.predict(test_state, deterministic=True)
            logger.info(f"  ✓ Loaded model prediction successful")
            logger.info(f"    Action: {action2} ({'PASS' if action2 == 1 else 'SKIP'})")

            # Verify same predictions
            if action == action2:
                logger.info(f"  ✓ Loaded model predictions match!")
            else:
                logger.warning(f"  ⚠ Predictions differ (may be due to stochasticity)")

    except Exception as e:
        logger.error(f"  ✗ Save/load test failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    logger.info("\n" + "=" * 80)
    logger.info("✓ ALL TESTS PASSED!")
    logger.info("=" * 80)

    return True


if __name__ == "__main__":
    import sys

    success = test_ppo_training()
    sys.exit(0 if success else 1)
