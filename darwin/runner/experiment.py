"""Main experiment runner implementing 10-step workflow."""

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from darwin.features.pipeline import FeaturePipeline
from darwin.llm.harness import LLMHarnessWithRetry
from darwin.llm.mock import MockLLM
from darwin.playbooks.base import PlaybookBase
from darwin.playbooks.breakout import BreakoutPlaybook
from darwin.playbooks.pullback import PullbackPlaybook
from darwin.runner.checkpointing import Checkpoint, load_checkpoint, save_checkpoint
from darwin.runner.progress import RunProgress
from darwin.schemas.candidate import CandidateRecordV1, PlaybookType
from darwin.schemas.decision_event import DecisionEventV1, DecisionType, SetupQuality
from darwin.schemas.llm_response import LLMResponseV1
from darwin.schemas.position import PositionRowV1
from darwin.schemas.run_config import RunConfigV1
from darwin.schemas.run_manifest import RunManifestV1
from darwin.simulator.position_manager import PositionManager
from darwin.storage.candidate_cache import CandidateCacheSQLite
from darwin.storage.position_ledger import PositionLedgerSQLite
from darwin.utils.helpers import compute_hash
from darwin.utils.logging import configure_logging
from darwin.utils.validation import validate_run_preflight

logger = logging.getLogger(__name__)


class ExperimentRunner:
    """
    Main experiment runner implementing 10-step workflow from spec.

    Workflow:
    1. Create/load run directory
    2. Snapshot run_config.json
    3. Validate config
    4. Compute config fingerprint
    5. Write manifest.json
    6. Iterate bars:
       - Build candidates (evaluate playbooks)
       - Compute features
       - Build LLM payload
       - Store payload (if enabled)
       - Call LLM
       - Store response (if enabled)
       - Parse decision
       - Cache candidate
       - Apply gate/budget
       - Emit DecisionEvent
       - Simulate trade if TAKE
    7. Close positions
    8. Build labels
    9. Build run report
    10. Update meta reports

    Example:
        >>> from darwin.schemas.run_config import RunConfigV1
        >>> config = RunConfigV1(...)
        >>> runner = ExperimentRunner(config)
        >>> runner.run()
    """

    def __init__(
        self,
        config: RunConfigV1,
        artifacts_dir: Optional[Path] = None,
        use_mock_llm: bool = False,
        resume_from_checkpoint: bool = False,
    ):
        """
        Initialize experiment runner.

        Args:
            config: Run configuration
            artifacts_dir: Artifacts directory (overrides config if provided)
            use_mock_llm: Use mock LLM instead of real API (default: False)
            resume_from_checkpoint: Resume from checkpoint if available (default: False)
        """
        self.config = config
        self.artifacts_dir = Path(artifacts_dir or config.artifacts_dir)
        self.run_dir = self.artifacts_dir / "runs" / config.run_id
        self.use_mock_llm = use_mock_llm
        self.resume_from_checkpoint = resume_from_checkpoint

        # Storage
        self.candidate_cache: Optional[CandidateCacheSQLite] = None
        self.position_ledger: Optional[PositionLedgerSQLite] = None

        # Components
        self.feature_pipeline: Optional[FeaturePipeline] = None
        self.llm_harness: Optional[LLMHarnessWithRetry] = None
        self.position_manager: Optional[PositionManager] = None
        self.playbooks: Dict[str, PlaybookBase] = {}

        # State
        self.manifest: Optional[RunManifestV1] = None
        self.checkpoint: Optional[Checkpoint] = None
        self.decision_events: List[DecisionEventV1] = []

        # Progress
        self.progress: Optional[RunProgress] = None

    def run(self) -> None:
        """
        Execute the full experiment workflow.

        This is the main entry point. It executes all 10 steps:
        1-5: Setup
        6: Main loop
        7-10: Teardown and reporting
        """
        try:
            # Steps 1-5: Setup
            self._setup()

            # Step 6: Main loop
            self._main_loop()

            # Steps 7-10: Teardown
            self._teardown()

        except Exception as e:
            logger.error(f"Experiment failed: {e}", exc_info=True)
            self._handle_failure(str(e))
            raise
        finally:
            self._cleanup()

    def _setup(self) -> None:
        """
        Execute setup steps 1-5.

        1. Create/load run directory
        2. Snapshot run_config.json
        3. Validate config
        4. Compute config fingerprint
        5. Write manifest.json
        """
        logger.info("=" * 80)
        logger.info(f"Starting experiment: {self.config.run_id}")
        logger.info("=" * 80)

        # Step 1: Create/load run directory
        logger.info("Step 1: Creating run directory")
        self.run_dir.mkdir(parents=True, exist_ok=True)
        (self.run_dir / "payloads").mkdir(exist_ok=True)
        (self.run_dir / "responses").mkdir(exist_ok=True)

        # Configure logging
        log_file = self.run_dir / "run.log"
        configure_logging(log_file=log_file, log_level="INFO", console_level="INFO")
        logger.info(f"Run directory: {self.run_dir}")

        # Step 2: Snapshot run_config.json
        logger.info("Step 2: Snapshotting run_config.json")
        config_path = self.run_dir / "run_config.json"
        with open(config_path, "w") as f:
            json.dump(self.config.model_dump(mode="json"), f, indent=2)
        logger.info(f"Config saved: {config_path}")

        # Step 3: Validate config
        logger.info("Step 3: Validating config")
        # Note: For now, skip data and LLM checks in validation
        # These will be checked when we actually try to load data / call LLM
        validate_run_preflight(self.config, check_llm=False, check_data=False)

        # Step 4: Compute config fingerprint
        logger.info("Step 4: Computing config fingerprint")
        config_hash = compute_hash(self.config.model_dump(mode="json"))
        logger.info(f"Config hash: {config_hash[:16]}...")

        # Step 5: Write manifest.json
        logger.info("Step 5: Writing manifest.json")
        self.manifest = RunManifestV1(
            header={
                "schema": "RunManifestV1",
                "created_at": datetime.now(),
                "run_id": self.config.run_id,
                "scope": "run",
                "generator": {"name": "darwin", "version": "0.1.0"},
            },
            started_at=datetime.now(),
            completed_at=None,
            status="running",
            content_hashes={"run_config": config_hash},
        )
        self._save_manifest()

        # Initialize storage
        logger.info("Initializing storage")
        self.candidate_cache = CandidateCacheSQLite(
            self.artifacts_dir / "candidate_cache" / "candidates.sqlite"
        )
        self.position_ledger = PositionLedgerSQLite(
            self.artifacts_dir / "ledger" / "positions.sqlite"
        )

        # Initialize components
        logger.info("Initializing components")
        self._initialize_playbooks()
        self._initialize_feature_pipeline()
        self._initialize_llm_harness()
        self._initialize_position_manager()

        # Load checkpoint if resuming
        if self.resume_from_checkpoint:
            checkpoint_path = self.run_dir / "checkpoint.json"
            self.checkpoint = load_checkpoint(checkpoint_path)
            if self.checkpoint:
                logger.info(f"Resuming from checkpoint: {self.checkpoint.bars_processed} bars processed")
            else:
                logger.info("No checkpoint found, starting from beginning")

        logger.info("Setup complete")

    def _main_loop(self) -> None:
        """
        Execute main loop (step 6).

        Iterate through bars and process candidates.
        """
        logger.info("Step 6: Main loop - processing bars")

        # For now, this is a stub since we don't have data loading yet
        # When data loading is implemented, this will:
        # - Load OHLCV data for all symbols/timeframes
        # - Iterate through bars
        # - For each bar:
        #   - Compute features
        #   - Evaluate playbooks
        #   - For each candidate:
        #     - Build LLM payload
        #     - Call LLM
        #     - Parse decision
        #     - Cache candidate
        #     - Apply gate/budget
        #     - Emit DecisionEvent
        #     - Simulate trade if TAKE

        logger.warning("Main loop is a stub - data loading not yet implemented")
        logger.info("Main loop complete (stub)")

    def _teardown(self) -> None:
        """
        Execute teardown steps 7-10.

        7. Close positions
        8. Build labels
        9. Build run report
        10. Update meta reports
        """
        logger.info("Steps 7-10: Teardown")

        # Step 7: Close positions
        logger.info("Step 7: Closing open positions")
        if self.position_manager:
            open_positions = self.position_ledger.list_positions(
                run_id=self.config.run_id, is_open=True
            )
            logger.info(f"  {len(open_positions)} positions to close")
            # TODO: Close positions at final bar

        # Step 8: Build labels
        logger.info("Step 8: Building outcome labels")
        # TODO: Build outcome labels

        # Step 9: Build run report
        logger.info("Step 9: Building run report")
        # TODO: Build run report

        # Step 10: Update meta reports
        logger.info("Step 10: Updating meta reports")
        # TODO: Update meta reports

        # Update manifest
        if self.manifest:
            self.manifest.completed_at = datetime.now()
            self.manifest.status = "completed"
            self._save_manifest()

        logger.info("Teardown complete")

    def _initialize_playbooks(self) -> None:
        """Initialize playbooks from config."""
        for pb_config in self.config.playbooks:
            if not pb_config.enabled:
                continue

            if pb_config.name == "breakout":
                self.playbooks["breakout"] = BreakoutPlaybook(pb_config)
            elif pb_config.name == "pullback":
                self.playbooks["pullback"] = PullbackPlaybook(pb_config)
            else:
                logger.warning(f"Unknown playbook: {pb_config.name}")

        logger.info(f"Initialized {len(self.playbooks)} playbooks: {list(self.playbooks.keys())}")

    def _initialize_feature_pipeline(self) -> None:
        """Initialize feature pipeline."""
        self.feature_pipeline = FeaturePipeline()
        logger.info("Feature pipeline initialized")

    def _initialize_llm_harness(self) -> None:
        """Initialize LLM harness."""
        if self.use_mock_llm:
            backend = MockLLM()
            logger.info("Using mock LLM")
        else:
            # TODO: Initialize real LLM backend when available
            logger.warning("Real LLM not yet implemented, using mock")
            backend = MockLLM()

        self.llm_harness = LLMHarnessWithRetry(
            backend=backend,
            max_retries=self.config.llm.max_retries,
            fallback_decision=self.config.llm.fallback_decision,
        )
        logger.info("LLM harness initialized")

    def _initialize_position_manager(self) -> None:
        """Initialize position manager."""
        self.position_manager = PositionManager(
            position_ledger=self.position_ledger,
            starting_equity_usd=self.config.portfolio.starting_equity_usd,
            max_positions=self.config.portfolio.max_positions,
            fee_maker_bps=self.config.fees.maker_bps,
            fee_taker_bps=self.config.fees.taker_bps,
        )
        logger.info("Position manager initialized")

    def _save_manifest(self) -> None:
        """Save manifest to disk."""
        if not self.manifest:
            return

        manifest_path = self.run_dir / "manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(self.manifest.model_dump(mode="json"), f, indent=2)

    def _handle_failure(self, error_message: str) -> None:
        """Handle experiment failure."""
        logger.error("Experiment failed, updating manifest")
        if self.manifest:
            self.manifest.status = "failed"
            self.manifest.error_message = error_message
            self.manifest.completed_at = datetime.now()
            self._save_manifest()

    def _cleanup(self) -> None:
        """Clean up resources."""
        logger.info("Cleaning up resources")
        if self.candidate_cache:
            self.candidate_cache.close()
        if self.position_ledger:
            self.position_ledger.close()
