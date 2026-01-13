"""Progress tracking for experiment runs."""

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from tqdm import tqdm

logger = logging.getLogger(__name__)


@dataclass
class ProgressStats:
    """Statistics tracked during run."""

    bars_processed: int = 0
    candidates_generated: int = 0
    trades_taken: int = 0
    llm_calls_made: int = 0
    llm_failures: int = 0
    start_time: float = field(default_factory=time.time)

    def elapsed_seconds(self) -> float:
        """Get elapsed time in seconds."""
        return time.time() - self.start_time

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "bars_processed": self.bars_processed,
            "candidates_generated": self.candidates_generated,
            "trades_taken": self.trades_taken,
            "llm_calls_made": self.llm_calls_made,
            "llm_failures": self.llm_failures,
            "elapsed_seconds": self.elapsed_seconds(),
        }


class RunProgress:
    """
    Thread-safe progress tracker for experiment runs.

    Tracks:
    - Bars processed
    - Candidates generated
    - Trades taken
    - LLM calls made
    - LLM failures

    Displays progress bar with tqdm and logs summary on completion.

    Example:
        >>> progress = RunProgress(total_bars=1000, description="Run test_001")
        >>> progress.start()
        >>> for i in range(1000):
        ...     progress.update_bar()
        ...     if i % 10 == 0:
        ...         progress.increment_candidate()
        >>> progress.finish()
    """

    def __init__(
        self,
        total_bars: int,
        description: str = "Processing",
        show_progress_bar: bool = True,
    ):
        """
        Initialize progress tracker.

        Args:
            total_bars: Total number of bars to process
            description: Description for progress bar (default: "Processing")
            show_progress_bar: Whether to show tqdm progress bar (default: True)
        """
        self.total_bars = total_bars
        self.description = description
        self.show_progress_bar = show_progress_bar

        self.stats = ProgressStats()
        self.pbar: Optional[tqdm] = None
        self.lock = threading.Lock()
        self.started = False
        self.finished = False

    def start(self) -> None:
        """Start progress tracking."""
        with self.lock:
            if self.started:
                logger.warning("Progress tracker already started")
                return

            self.started = True
            self.stats.start_time = time.time()

            if self.show_progress_bar:
                self.pbar = tqdm(
                    total=self.total_bars,
                    desc=self.description,
                    unit="bar",
                    ncols=100,
                    bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
                )

            logger.info(f"Progress tracker started: {self.description}")

    def update_bar(self, n: int = 1) -> None:
        """
        Update bars processed.

        Args:
            n: Number of bars to increment (default: 1)
        """
        with self.lock:
            self.stats.bars_processed += n
            if self.pbar:
                self.pbar.update(n)

    def increment_candidate(self) -> None:
        """Increment candidates generated count."""
        with self.lock:
            self.stats.candidates_generated += 1
            self._update_postfix()

    def increment_trade(self) -> None:
        """Increment trades taken count."""
        with self.lock:
            self.stats.trades_taken += 1
            self._update_postfix()

    def increment_llm_call(self) -> None:
        """Increment LLM calls made count."""
        with self.lock:
            self.stats.llm_calls_made += 1
            self._update_postfix()

    def increment_llm_failure(self) -> None:
        """Increment LLM failures count."""
        with self.lock:
            self.stats.llm_failures += 1
            self._update_postfix()

    def _update_postfix(self) -> None:
        """Update progress bar postfix with current stats."""
        if self.pbar:
            postfix = (
                f"candidates={self.stats.candidates_generated} "
                f"trades={self.stats.trades_taken} "
                f"llm={self.stats.llm_calls_made}"
            )
            if self.stats.llm_failures > 0:
                postfix += f" (failures={self.stats.llm_failures})"
            self.pbar.set_postfix_str(postfix)

    def get_stats(self) -> ProgressStats:
        """
        Get current statistics.

        Returns:
            Copy of current ProgressStats
        """
        with self.lock:
            # Return a copy to avoid mutation
            return ProgressStats(
                bars_processed=self.stats.bars_processed,
                candidates_generated=self.stats.candidates_generated,
                trades_taken=self.stats.trades_taken,
                llm_calls_made=self.stats.llm_calls_made,
                llm_failures=self.stats.llm_failures,
                start_time=self.stats.start_time,
            )

    def finish(self) -> None:
        """Finish progress tracking and log summary."""
        with self.lock:
            if self.finished:
                logger.warning("Progress tracker already finished")
                return

            self.finished = True

            if self.pbar:
                self.pbar.close()

            # Log summary
            elapsed = self.stats.elapsed_seconds()
            logger.info("=" * 80)
            logger.info(f"Run completed: {self.description}")
            logger.info(f"  Bars processed:       {self.stats.bars_processed:,}")
            logger.info(f"  Candidates generated: {self.stats.candidates_generated:,}")
            logger.info(f"  Trades taken:         {self.stats.trades_taken:,}")
            logger.info(f"  LLM calls made:       {self.stats.llm_calls_made:,}")
            if self.stats.llm_failures > 0:
                logger.info(f"  LLM failures:         {self.stats.llm_failures:,}")
            logger.info(f"  Elapsed time:         {elapsed:.1f}s")
            if self.stats.bars_processed > 0:
                bars_per_sec = self.stats.bars_processed / elapsed
                logger.info(f"  Throughput:           {bars_per_sec:.1f} bars/sec")
            logger.info("=" * 80)

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.finish()
