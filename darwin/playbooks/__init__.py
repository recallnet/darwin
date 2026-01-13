"""Darwin playbooks module.

This module contains all trading playbook implementations. Each playbook defines:
1. Entry conditions (when to generate a candidate)
2. Exit specifications (stop loss, take profit, trailing, time stop)
3. Quality indicators (flags that describe setup quality)

Available Playbooks:
    - BreakoutPlaybook: Range breakout with trend + volume confirmation
    - PullbackPlaybook: Dip-buy in uptrend with EMA tag and reclaim
"""

from darwin.playbooks.base import CandidateInfo, PlaybookBase
from darwin.playbooks.breakout import BreakoutPlaybook
from darwin.playbooks.pullback import PullbackPlaybook

__all__ = [
    # Base classes
    "PlaybookBase",
    "CandidateInfo",
    # Playbook implementations
    "BreakoutPlaybook",
    "PullbackPlaybook",
]
