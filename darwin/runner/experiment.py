"""Main experiment runner implementing 10-step workflow."""

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from darwin.features.pipeline import FeaturePipelineV1 as FeaturePipeline
from darwin.llm.harness import LLMHarnessWithRetry
from darwin.llm.mock import MockLLM
from darwin.playbooks.base import PlaybookBase
from darwin.playbooks.breakout import BreakoutPlaybook
from darwin.playbooks.pullback import PullbackPlaybook
from darwin.runner.checkpointing import Checkpoint, load_checkpoint, save_checkpoint
from darwin.runner.llm_history import LLMHistoryTracker
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

# RL system (optional)
try:
    from darwin.rl.integration.runner_hooks import RLSystem
    RL_AVAILABLE = True
except ImportError:
    RL_AVAILABLE = False
    RLSystem = None

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

        # Components (one pipeline per symbol)
        self.feature_pipelines: Dict[str, FeaturePipeline] = {}
        self.llm_harness: Optional[LLMHarnessWithRetry] = None
        self.position_manager: Optional[PositionManager] = None
        self.playbooks: Dict[str, PlaybookBase] = {}
        self.rl_system: Optional[RLSystem] = None
        self.llm_history: Optional[LLMHistoryTracker] = None
        self.degradation_monitor: Optional[object] = None  # DegradationMonitor

        # Track graduation metrics for degradation checking
        self.graduation_metrics: Dict[str, float] = {}

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
        self._initialize_rl_system()
        self._initialize_llm_history()
        self._initialize_degradation_monitor()

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

        # Import data loader
        from darwin.utils.data_loader import load_ohlcv_data
        import pandas as pd

        # Step 1: Load OHLCV data for all symbols and timeframes
        logger.info(f"Loading OHLCV data for {len(self.config.market_scope.symbols)} symbols")

        # Get all timeframes (primary + additional)
        all_timeframes = [self.config.market_scope.primary_timeframe] + self.config.market_scope.additional_timeframes

        # Data structure: {symbol: {timeframe: DataFrame}}
        ohlcv_data = {}

        for symbol in self.config.market_scope.symbols:
            ohlcv_data[symbol] = {}
            for tf in all_timeframes:
                try:
                    # Only allow synthetic data in mock mode
                    df = load_ohlcv_data(
                        symbol=symbol,
                        timeframe=tf,
                        start_date=self.config.market_scope.start_date,
                        end_date=self.config.market_scope.end_date,
                        allow_synthetic=self.use_mock_llm,
                    )
                    ohlcv_data[symbol][tf] = df
                    logger.info(f"  Loaded {len(df)} bars for {symbol} {tf}")
                except Exception as e:
                    logger.error(f"  Failed to load {symbol} {tf}: {e}")
                    raise

        # Step 2: Get common timestamps from primary timeframe
        # Use the primary timeframe for iteration
        primary_tf = self.config.market_scope.primary_timeframe

        # Find intersection of timestamps across all symbols
        timestamp_sets = []
        for symbol in self.config.market_scope.symbols:
            if primary_tf in ohlcv_data[symbol]:
                timestamp_sets.append(set(ohlcv_data[symbol][primary_tf]['timestamp']))

        if not timestamp_sets:
            logger.warning("No data loaded for any symbol")
            return

        common_timestamps = sorted(timestamp_sets[0].intersection(*timestamp_sets[1:]))
        logger.info(f"Found {len(common_timestamps)} common timestamps for iteration")

        # Step 3: Initialize counters
        bars_processed = 0
        candidates_generated = 0
        trades_taken = 0
        llm_calls_made = 0
        llm_failures = 0
        trades_skipped_no_capital = 0

        # Initialize equity tracking
        current_equity = self.config.portfolio.starting_equity_usd
        realized_pnl = 0.0

        logger.info(f"Starting equity: ${current_equity:,.2f}")
        logger.info(f"Max exposure allowed: {self.config.portfolio.max_exposure_fraction * 100:.1f}% (${current_equity * self.config.portfolio.max_exposure_fraction:,.2f})")
        logger.info(f"Position sizing method: {self.config.portfolio.position_size_method}")
        if self.config.portfolio.position_size_method == "risk_parity":
            logger.info(f"Risk per trade: {self.config.portfolio.risk_per_trade_fraction * 100:.2f}%")

        # Step 4: Iterate through bars
        logger.info(f"Starting main loop with {len(common_timestamps)} bars to process")
        for i, timestamp in enumerate(common_timestamps):
            bars_processed += 1

            # Log every bar if near warmup to debug hang
            if bars_processed >= 19 and bars_processed <= 25:
                logger.info(f"Processing bar {bars_processed}/{len(common_timestamps)}")

            # Log progress every 100 bars (or every 10 for small tests)
            if bars_processed % 10 == 0 or bars_processed == 1:
                logger.info(f"Progress: {bars_processed}/{len(common_timestamps)} bars, "
                           f"{candidates_generated} candidates, {trades_taken} trades, "
                           f"{llm_calls_made} LLM calls ({llm_failures} failures)")

            # Check for agent degradation every 100 bars
            if bars_processed % 100 == 0 and bars_processed > 100:
                self._check_agent_degradation()

            # Process each symbol
            for symbol in self.config.market_scope.symbols:
                # Get current bar data for this symbol
                df = ohlcv_data[symbol][primary_tf]
                bar_idx = df[df['timestamp'] == timestamp].index

                if len(bar_idx) == 0:
                    continue

                bar_idx = bar_idx[0]
                bar = df.iloc[bar_idx]

                # Update feature pipeline for this symbol
                pipeline = self.feature_pipelines[symbol]

                # Convert timestamp to unix seconds (int)
                timestamp_unix = int(bar['timestamp'].timestamp())

                # Get portfolio state for this symbol
                open_positions = len([p for p in self.position_ledger.list_positions(
                    run_id=self.config.run_id, is_open=True
                ) if p.symbol == symbol])

                # Calculate current exposure
                all_open_positions = self.position_ledger.list_positions(
                    run_id=self.config.run_id, is_open=True
                )
                current_exposure = sum(p.size_usd for p in all_open_positions if p.size_usd)
                exposure_frac = current_exposure / current_equity if current_equity > 0 else 0.0

                # Calculate 24h drawdown (simplified: use equity drawdown from peak)
                # Track equity high water mark
                if not hasattr(self, 'equity_high_water_mark'):
                    self.equity_high_water_mark = self.config.portfolio.starting_equity_usd

                if current_equity > self.equity_high_water_mark:
                    self.equity_high_water_mark = current_equity

                drawdown_usd = self.equity_high_water_mark - current_equity
                dd_24h_bps = (drawdown_usd / self.equity_high_water_mark * 10000.0) if self.equity_high_water_mark > 0 else 0.0

                # Call on_bar to compute features
                logger.debug(f"Bar {bars_processed}: Computing features for {symbol}")
                features = pipeline.on_bar(
                    timestamp=timestamp_unix,
                    open_price=float(bar['open']),
                    high=float(bar['high']),
                    low=float(bar['low']),
                    close=float(bar['close']),
                    volume=float(bar['volume']),
                    open_positions=open_positions,
                    exposure_frac=exposure_frac,
                    dd_24h_bps=dd_24h_bps,
                    halt_flag=0,
                )

                # Skip if features not ready (warmup period)
                if features is None:
                    logger.debug(f"Bar {bars_processed}: Features not ready (warmup)")
                    continue

                logger.debug(f"Bar {bars_processed}: Features ready, evaluating playbooks")

                # Prepare bar_data dict for playbook evaluation
                bar_data = {
                    'open': float(bar['open']),
                    'high': float(bar['high']),
                    'low': float(bar['low']),
                    'close': float(bar['close']),
                    'volume': float(bar['volume']),
                }

                # Evaluate each playbook
                for playbook_name, playbook in self.playbooks.items():
                    candidate_info = playbook.evaluate(features, bar_data)

                    if candidate_info is None:
                        continue  # No entry signal

                    candidates_generated += 1
                    logger.debug(f"Candidate #{candidates_generated} generated: {symbol} at {timestamp}")

                    # Generate candidate ID
                    candidate_id = f"{symbol}_{timestamp.strftime('%Y%m%d_%H%M%S')}_{playbook_name}"

                    # Build portfolio state for RL agents
                    open_positions_list = self.position_ledger.list_positions(
                        run_id=self.config.run_id, is_open=True
                    )
                    current_exposure = sum(pos.size_usd for pos in open_positions_list if pos.size_usd)
                    max_exposure = current_equity * self.config.portfolio.max_exposure_fraction
                    available_capacity = max_exposure - current_exposure

                    portfolio_state = {
                        "current_equity_usd": current_equity,
                        "open_positions": len(open_positions_list),
                        "max_positions": self.config.portfolio.max_positions,
                        "exposure_frac": exposure_frac,
                        "max_exposure_frac": self.config.portfolio.max_exposure_fraction,
                        "dd_24h_bps": dd_24h_bps,
                        "halt_flag": 0,  # TODO: Implement halt logic
                        "available_capacity": available_capacity,
                    }

                    # Create preliminary candidate record for RL gate hook
                    from darwin.schemas.candidate import CandidateRecordV1, PlaybookType

                    candidate_record = CandidateRecordV1(
                        candidate_id=candidate_id,
                        run_id=self.config.run_id,
                        timestamp=timestamp,
                        symbol=symbol,
                        timeframe=primary_tf,
                        bar_index=bars_processed,
                        playbook=PlaybookType(playbook_name),
                        direction="long",
                        entry_price=candidate_info.entry_price,
                        atr_at_entry=candidate_info.atr_at_entry,
                        exit_spec=candidate_info.exit_spec,
                        features=features,
                        llm_decision=None,  # Not yet determined
                        llm_confidence=None,
                        llm_setup_quality=None,
                        payload_ref=None,
                        response_ref=None,
                        was_taken=False,
                        rejection_reason=None,
                        position_id=None,
                    )

                    # RL Gate Hook: Check if gate agent wants to skip before LLM call
                    # Note: gate_hook handles observe vs active mode internally
                    if self.rl_system:
                        gate_decision = self.rl_system.gate_hook(candidate_record, portfolio_state)
                        if gate_decision == "skip":
                            logger.debug(f"Gate agent (active) skipped candidate {candidate_id}")
                            candidate_record.rejection_reason = "gate_agent_skip"
                            self.candidate_cache.put(candidate_record)
                            continue  # Skip LLM call

                    # Build LLM payload (simplified format for now)
                    llm_payload = {
                        "system": (
                            "You are a professional cryptocurrency trader. "
                            "Analyze the trading setup and decide whether to TAKE or SKIP the trade. "
                            "Respond with JSON: {\"decision\": \"take\" or \"skip\", \"confidence\": 0.0-1.0, \"reasoning\": \"brief explanation\", \"setup_quality\": \"A+\", \"A\", \"A-\", \"B\", or \"C\"}"
                        ),
                        "user": (
                            f"Symbol: {symbol}\n"
                            f"Playbook: {playbook_name}\n"
                            f"Entry Price: ${candidate_info.entry_price:.2f}\n"
                            f"ATR: ${candidate_info.atr_at_entry:.2f}\n"
                            f"Stop Loss: ${candidate_info.exit_spec.stop_loss_price:.2f} "
                            f"({abs(candidate_info.entry_price - candidate_info.exit_spec.stop_loss_price) / candidate_info.atr_at_entry:.2f}R)\n"
                            f"Take Profit: ${candidate_info.exit_spec.take_profit_price:.2f} "
                            f"({abs(candidate_info.exit_spec.take_profit_price - candidate_info.entry_price) / candidate_info.atr_at_entry:.2f}R)\n"
                            f"\nKey Features:\n" +
                            "\n".join([f"  {k}: {v:.4f}" for k, v in list(features.items())[:10]])
                        )
                    }

                    # Call LLM for decision
                    logger.debug(f"Calling LLM for candidate {candidate_id}...")
                    llm_result = self.llm_harness.query(llm_payload)
                    llm_calls_made += 1
                    logger.debug(f"LLM call completed, success={llm_result.success}")

                    if not llm_result.success:
                        llm_failures += 1

                    # Extract decision
                    if llm_result.success and llm_result.response:
                        decision = llm_result.response.decision.lower()
                        llm_confidence = llm_result.response.confidence
                        llm_setup_quality = llm_result.response.setup_quality
                    else:
                        # Fallback
                        decision = self.config.llm.fallback_decision.lower()
                        llm_confidence = 0.0
                        llm_setup_quality = None

                    # Update candidate record with LLM decision
                    candidate_record.llm_decision = decision
                    candidate_record.llm_confidence = llm_confidence
                    candidate_record.llm_setup_quality = llm_setup_quality
                    candidate_record.was_taken = (decision == "take")
                    candidate_record.rejection_reason = None if decision == "take" else "llm_decided_skip"

                    # Record LLM decision in history tracker
                    if self.llm_history:
                        self.llm_history.record_decision(
                            candidate_id=candidate_id,
                            symbol=symbol,
                            playbook=playbook_name,
                            llm_decision=decision,
                            llm_confidence=llm_confidence if llm_confidence else 0.0,
                            llm_setup_quality=llm_setup_quality if llm_setup_quality else "C",
                            timestamp=timestamp.isoformat(),
                        )

                    # RL Meta-Learner Hook: Check if meta-learner wants to override LLM
                    # Note: meta_learner_hook handles observe vs active mode internally
                    if self.rl_system:
                        # Build LLM response dict
                        llm_response = {
                            "decision": decision,
                            "confidence": llm_confidence,
                            "setup_quality": llm_setup_quality,
                            "risk_flags": [],  # TODO: Extract from LLM response
                            "notes": llm_result.response.notes if (llm_result.response and llm_result.response.notes) else "",
                        }

                        # Build LLM history from tracker
                        if self.llm_history:
                            llm_history = self.llm_history.get_llm_history_dict()
                            # Add playbook and symbol specific accuracies
                            llm_history["playbook_llm_accuracy"] = self.llm_history.get_playbook_accuracy(playbook_name)
                            llm_history["symbol_llm_accuracy"] = self.llm_history.get_symbol_accuracy(symbol)
                        else:
                            # Fallback if no history tracker
                            llm_history = {
                                "llm_recent_accuracy": 0.5,
                                "llm_recent_sharpe": 0.0,
                                "playbook_llm_accuracy": 0.5,
                                "symbol_llm_accuracy": 0.5,
                                "market_regime": "neutral",
                                "llm_streak": 0,
                            }

                        override_decision = self.rl_system.meta_learner_hook(
                            candidate_record, llm_response, llm_history, portfolio_state
                        )

                        if override_decision:
                            logger.debug(
                                f"Meta-learner overriding LLM '{decision}' -> '{override_decision}' "
                                f"for candidate {candidate_id}"
                            )
                            decision = override_decision
                            candidate_record.llm_decision = decision
                            candidate_record.was_taken = (decision == "take")
                            candidate_record.rejection_reason = (
                                None if decision == "take" else "meta_learner_override_skip"
                            )

                    # Cache candidate
                    self.candidate_cache.put(candidate_record)

                    if decision == "take":
                        # Calculate base position size based on portfolio config
                        position_size_usd = None

                        if self.config.portfolio.position_size_method == "risk_parity":
                            # Risk-based sizing: risk X% of equity per trade
                            risk_per_trade = self.config.portfolio.risk_per_trade_fraction
                            risk_amount_usd = current_equity * risk_per_trade

                            # Calculate stop distance as percentage
                            entry_price = candidate_info.entry_price
                            stop_price = candidate_info.exit_spec.stop_loss_price
                            stop_distance_pct = abs(entry_price - stop_price) / entry_price

                            if stop_distance_pct > 0:
                                position_size_usd = risk_amount_usd / stop_distance_pct
                            else:
                                logger.warning(f"Invalid stop distance for {symbol}, skipping trade")
                                trades_skipped_no_capital += 1
                                continue

                        elif self.config.portfolio.position_size_method == "equal_weight":
                            # Equal weight: divide available capital by max_positions
                            # Note: This doesn't work well with high max_positions
                            max_positions = self.config.portfolio.max_positions
                            if max_positions > 0:
                                position_size_usd = (current_equity * self.config.portfolio.max_exposure_fraction) / max_positions
                            else:
                                position_size_usd = current_equity * 0.10  # Fallback: 10% per position

                        # RL Portfolio Hook: Adjust position size
                        # Note: portfolio_hook handles observe vs active mode internally
                        position_size_fraction = 1.0  # Default: full size
                        if self.rl_system:
                            llm_response = {
                                "decision": decision,
                                "confidence": llm_confidence,
                                "setup_quality": llm_setup_quality,
                                "risk_flags": [],
                                "notes": "",
                            }
                            position_size_fraction = self.rl_system.portfolio_hook(
                                candidate_record, llm_response, portfolio_state
                            )
                            logger.debug(
                                f"Portfolio agent adjusted position size by {position_size_fraction:.2f}x "
                                f"for candidate {candidate_id}"
                            )

                        # Apply portfolio agent adjustment
                        position_size_usd = position_size_usd * position_size_fraction

                        # Calculate current exposure from open positions
                        open_positions = self.position_ledger.list_positions(
                            run_id=self.config.run_id, is_open=True
                        )
                        current_exposure = sum(pos.size_usd for pos in open_positions if pos.size_usd)
                        max_exposure = current_equity * self.config.portfolio.max_exposure_fraction

                        # Check if we have enough capital
                        if current_exposure + position_size_usd > max_exposure:
                            logger.debug(
                                f"Insufficient capital: current=${current_exposure:,.0f}, "
                                f"new=${position_size_usd:,.0f}, max=${max_exposure:,.0f}"
                            )
                            trades_skipped_no_capital += 1
                            candidate_record.was_taken = False
                            candidate_record.rejection_reason = "insufficient_capital"
                            self.candidate_cache.put(candidate_record)
                            continue

                        # Simulate trade entry
                        try:
                            # Get next bar's open price for fill simulation
                            if bar_idx + 1 < len(df):
                                next_bar = df.iloc[bar_idx + 1]
                                next_open = float(next_bar['open'])
                            else:
                                # Use current close if no next bar (end of data)
                                next_open = float(bar['close'])
                                logger.warning(f"No next bar for fill simulation, using current close")

                            position_id = self.position_manager.open_position(
                                candidate_id=candidate_id,
                                symbol=symbol,
                                direction="long",
                                signal_price=candidate_info.entry_price,
                                next_open=next_open,
                                bar_index=bars_processed,
                                timestamp=timestamp,
                                size_usd=position_size_usd,
                                atr_at_entry=candidate_info.atr_at_entry,
                                exit_spec=candidate_info.exit_spec,
                            )

                            trades_taken += 1
                            logger.debug(
                                f"Opened position: {symbol} @ ${candidate_info.entry_price:.2f}, "
                                f"size=${position_size_usd:,.0f}, exposure={current_exposure + position_size_usd:,.0f}/{max_exposure:,.0f}"
                            )

                            # Update candidate record with position ID
                            candidate_record.position_id = position_id
                            self.candidate_cache.put(candidate_record)  # Update the record

                        except Exception as e:
                            logger.error(f"Failed to open position: {e}")

                # Update open positions for this symbol (check for exits)
                if self.position_manager:
                    # Update positions for this symbol with current bar data
                    closed_position_ids = self.position_manager.update_positions(
                        high=float(bar['high']),
                        low=float(bar['low']),
                        close=float(bar['close']),
                        bar_index=bars_processed,
                        timestamp=timestamp,
                    )

                    # Update equity with realized PnL from closed positions
                    if closed_position_ids:
                        for position_id in closed_position_ids:
                            closed_pos = self.position_ledger.get_position(position_id)
                            if closed_pos and closed_pos.pnl_usd is not None:
                                realized_pnl += closed_pos.pnl_usd
                                current_equity = self.config.portfolio.starting_equity_usd + realized_pnl
                                logger.debug(f"Position closed: {position_id}, PnL: ${closed_pos.pnl_usd:,.2f}, New equity: ${current_equity:,.2f}")

                                # RL Outcome Update: Record outcome for RL agents
                                if self.rl_system and closed_pos.candidate_id:
                                    self.rl_system.update_decision_outcome(
                                        candidate_id=closed_pos.candidate_id,
                                        r_multiple=closed_pos.r_multiple,
                                        pnl_usd=closed_pos.pnl_usd,
                                    )
                                    logger.debug(
                                        f"Updated RL outcome for candidate {closed_pos.candidate_id}: "
                                        f"R={closed_pos.r_multiple:.2f}, PnL=${closed_pos.pnl_usd:.2f}"
                                    )

                                # LLM History Update: Record outcome for LLM performance tracking
                                if self.llm_history and closed_pos.candidate_id:
                                    self.llm_history.update_outcome(
                                        candidate_id=closed_pos.candidate_id,
                                        r_multiple=closed_pos.r_multiple if closed_pos.r_multiple else 0.0,
                                        pnl_usd=closed_pos.pnl_usd,
                                    )

        # Step 5: Update manifest with final counts
        if self.manifest:
            self.manifest.bars_processed = bars_processed
            self.manifest.candidates_generated = candidates_generated
            self.manifest.trades_taken = trades_taken
            self.manifest.llm_calls_made = llm_calls_made
            self.manifest.llm_failures = llm_failures
            self._save_manifest()

        logger.info(f"Main loop complete: {bars_processed} bars, {candidates_generated} candidates, "
                   f"{trades_taken} trades, {llm_calls_made} LLM calls ({llm_failures} failures)")
        logger.info(f"Final equity: ${current_equity:,.2f} (realized PnL: ${realized_pnl:,.2f})")
        if trades_skipped_no_capital > 0:
            logger.info(f"Trades skipped due to insufficient capital: {trades_skipped_no_capital}")

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
            elif pb_config.name == "always_signal":
                from darwin.playbooks.always_signal import AlwaysSignalPlaybook
                self.playbooks["always_signal"] = AlwaysSignalPlaybook(
                    stop_loss_atr=pb_config.stop_loss_atr,
                    take_profit_atr=pb_config.take_profit_atr,
                    time_stop_bars=pb_config.time_stop_bars,
                    trailing_activation_atr=pb_config.trailing_activation_atr,
                    trailing_distance_atr=pb_config.trailing_distance_atr,
                )
            else:
                logger.warning(f"Unknown playbook: {pb_config.name}")

        logger.info(f"Initialized {len(self.playbooks)} playbooks: {list(self.playbooks.keys())}")

    def _initialize_feature_pipeline(self) -> None:
        """Initialize feature pipelines (one per symbol)."""
        for symbol in self.config.market_scope.symbols:
            self.feature_pipelines[symbol] = FeaturePipeline(
                symbol=symbol,
                warmup_bars=self.config.market_scope.warmup_bars,
                spread_bps=self.config.fees.maker_bps,  # Use maker fee as spread estimate
            )
        logger.info(f"Feature pipelines initialized for {len(self.feature_pipelines)} symbols")

    def _initialize_llm_harness(self) -> None:
        """Initialize LLM harness."""
        from darwin.llm.backend import create_llm_backend
        from darwin.llm.rate_limiter import RateLimiter

        if self.use_mock_llm:
            backend = MockLLM()
            logger.info("Using mock LLM")
        else:
            # Initialize real LLM backend using Vercel AI Gateway
            try:
                backend = create_llm_backend(
                    provider=self.config.llm.provider,
                    model=self.config.llm.model,
                    temperature=self.config.llm.temperature,
                    max_tokens=self.config.llm.max_tokens,
                    use_mock=False,
                )
                logger.info(f"Using real LLM: {self.config.llm.provider}/{self.config.llm.model}")
            except Exception as e:
                logger.error(f"Failed to initialize real LLM: {e}")
                logger.warning("Falling back to mock LLM")
                backend = MockLLM()

        # Create rate limiter if max_calls_per_minute is specified
        rate_limiter = None
        if hasattr(self.config.llm, 'max_calls_per_minute') and self.config.llm.max_calls_per_minute > 0:
            rate_limiter = RateLimiter(max_calls_per_minute=self.config.llm.max_calls_per_minute)
            logger.info(f"Rate limiter initialized: {self.config.llm.max_calls_per_minute} calls/minute")

        self.llm_harness = LLMHarnessWithRetry(
            backend=backend,
            max_retries=self.config.llm.max_retries,
            fallback_decision=self.config.llm.fallback_decision,
            rate_limiter=rate_limiter,
        )
        logger.info("LLM harness initialized")

    def _initialize_position_manager(self) -> None:
        """Initialize position manager."""
        self.position_manager = PositionManager(
            ledger=self.position_ledger,
            run_id=self.config.run_id,
            fee_maker_bps=self.config.fees.maker_bps,
            fee_taker_bps=self.config.fees.taker_bps,
        )
        logger.info("Position manager initialized")

    def _initialize_rl_system(self) -> None:
        """Initialize RL system if configured."""
        if not self.config.rl:
            logger.info("RL system not configured")
            return

        if not RL_AVAILABLE:
            logger.warning("RL system configured but RL dependencies not installed")
            return

        try:
            self.rl_system = RLSystem(config=self.config.rl, run_id=self.config.run_id)
            logger.info("RL system initialized")

            # Check graduation status and auto-switch modes if graduated
            self._check_and_auto_switch_agent_modes()

            # Log agent status
            if self.config.rl.gate_agent and self.config.rl.gate_agent.enabled:
                mode = self.config.rl.gate_agent.mode
                status = self.config.rl.gate_agent.current_status
                active = self.rl_system.gate_agent_active()
                logger.info(f"  Gate agent: {mode} mode, status={status}, active={active}")

            if self.config.rl.portfolio_agent and self.config.rl.portfolio_agent.enabled:
                mode = self.config.rl.portfolio_agent.mode
                status = self.config.rl.portfolio_agent.current_status
                logger.info(f"  Portfolio agent: {mode} mode, status={status}")

            if self.config.rl.meta_learner_agent and self.config.rl.meta_learner_agent.enabled:
                mode = self.config.rl.meta_learner_agent.mode
                status = self.config.rl.meta_learner_agent.current_status
                logger.info(f"  Meta-learner agent: {mode} mode, status={status}")

        except Exception as e:
            logger.error(f"Failed to initialize RL system: {e}")
            self.rl_system = None

    def _initialize_llm_history(self) -> None:
        """Initialize LLM history tracker for meta-learning."""
        self.llm_history = LLMHistoryTracker(window_size=100)
        logger.info("LLM history tracker initialized")

    def _initialize_degradation_monitor(self) -> None:
        """Initialize degradation monitor for active agents."""
        if not self.config.rl or not RL_AVAILABLE:
            return

        try:
            from darwin.rl.monitoring.degradation import DegradationMonitor

            agent_state_db_path = self.config.rl.agent_state_db
            self.degradation_monitor = DegradationMonitor(
                agent_state_db=self.rl_system.agent_state if self.rl_system else None,
                lookback_window=100,
                degradation_threshold_pct=25.0,  # 25% performance drop triggers rollback
                min_samples_for_check=50,
            )

            # Load graduation metrics from agent configs
            if self.config.rl.gate_agent and self.config.rl.gate_agent.enabled:
                # Use min_validation_metric as baseline
                self.graduation_metrics["gate"] = self.config.rl.gate_agent.graduation_thresholds.min_validation_metric

            if self.config.rl.portfolio_agent and self.config.rl.portfolio_agent.enabled:
                self.graduation_metrics["portfolio"] = self.config.rl.portfolio_agent.graduation_thresholds.min_validation_metric

            if self.config.rl.meta_learner_agent and self.config.rl.meta_learner_agent.enabled:
                self.graduation_metrics["meta_learner"] = self.config.rl.meta_learner_agent.graduation_thresholds.min_validation_metric

            logger.info("Degradation monitor initialized")

        except Exception as e:
            logger.warning(f"Failed to initialize degradation monitor: {e}")
            self.degradation_monitor = None

    def _check_and_auto_switch_agent_modes(self) -> None:
        """Check agent graduation status and auto-switch to active mode if graduated.

        For each agent:
        1. Check if status = "graduated"
        2. Check if mode = "observe"
        3. If both true: switch to active mode
        """
        if not self.rl_system or not self.config.rl:
            return

        agents_switched = []

        # Check gate agent
        if self.config.rl.gate_agent and self.config.rl.gate_agent.enabled:
            if (
                self.config.rl.gate_agent.current_status == "graduated"
                and self.config.rl.gate_agent.mode == "observe"
            ):
                logger.info("🎓 Gate agent has graduated! Switching to active mode...")
                self.config.rl.gate_agent.mode = "active"
                agents_switched.append("gate")

        # Check portfolio agent
        if self.config.rl.portfolio_agent and self.config.rl.portfolio_agent.enabled:
            if (
                self.config.rl.portfolio_agent.current_status == "graduated"
                and self.config.rl.portfolio_agent.mode == "observe"
            ):
                logger.info("🎓 Portfolio agent has graduated! Switching to active mode...")
                self.config.rl.portfolio_agent.mode = "active"
                agents_switched.append("portfolio")

        # Check meta-learner agent
        if self.config.rl.meta_learner_agent and self.config.rl.meta_learner_agent.enabled:
            if (
                self.config.rl.meta_learner_agent.current_status == "graduated"
                and self.config.rl.meta_learner_agent.mode == "observe"
            ):
                logger.info("🎓 Meta-learner agent has graduated! Switching to active mode...")
                self.config.rl.meta_learner_agent.mode = "active"
                agents_switched.append("meta_learner")

        if agents_switched:
            logger.info(f"Auto-switched {len(agents_switched)} agent(s) to active mode: {', '.join(agents_switched)}")
        else:
            logger.info("No agents ready for auto-graduation")

    def _check_agent_degradation(self) -> None:
        """Check active agents for performance degradation and auto-rollback if needed."""
        if not self.degradation_monitor or not self.rl_system or not self.config.rl:
            return

        # Check all active agents
        results = self.degradation_monitor.check_all_agents(
            gate_config=self.config.rl.gate_agent,
            portfolio_config=self.config.rl.portfolio_agent,
            meta_learner_config=self.config.rl.meta_learner_agent,
            graduation_metrics=self.graduation_metrics,
        )

        # Handle any degraded agents
        for agent_name, (is_degraded, details) in results.items():
            if is_degraded and details:
                logger.error(f"")
                logger.error(f"{'='*80}")
                logger.error(f"⚠️  AGENT DEGRADATION DETECTED: {agent_name}")
                logger.error(f"{'='*80}")
                logger.error(f"Performance dropped: {details['performance_drop_pct']:.1f}%")
                logger.error(f"Graduation metric: {details['graduation_metric']:.3f}")
                logger.error(f"Current metric: {details['current_metric']:.3f}")
                logger.error(f"")

                # Auto-rollback
                agent_config = {
                    "gate": self.config.rl.gate_agent,
                    "portfolio": self.config.rl.portfolio_agent,
                    "meta_learner": self.config.rl.meta_learner_agent,
                }.get(agent_name)

                if agent_config:
                    self.degradation_monitor.rollback_agent(agent_config)
                    logger.error(f"Agent '{agent_name}' has been rolled back to observe mode")
                    logger.error(f"{'='*80}")
                    logger.error(f"")

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
        if self.rl_system:
            self.rl_system.close()
