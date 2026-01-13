"""Reinforcement Learning module for Darwin trading system.

This module implements a multi-agent RL system with:
- Gate Agent: Filters candidates before LLM (reduces API costs)
- Portfolio Agent: Optimizes position sizing
- Meta-Learner Agent: Overrides/adjusts LLM decisions

All agents use PPO and graduate from observe → active mode based on performance.
"""

__version__ = "0.1.0"
