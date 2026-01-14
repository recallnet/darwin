"""Neural network architectures for RL agents.

Simple feed-forward networks for the three agent types:
- Gate Agent: Binary classification (pass/skip)
- Portfolio Agent: Regression (position size fraction)
- Meta-Learner Agent: Multi-class classification (agree/override_skip/override_take)
"""

import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger.warning("PyTorch not available. Install with: pip install torch")


if TORCH_AVAILABLE:
    class GateAgentNetwork(nn.Module):
        """Neural network for Gate Agent.

        Input: Candidate features (34 dims from state encoder)
        Output: Binary decision (skip=0, pass=1)
        """

        def __init__(self, state_dim: int = 34, hidden_dims: list = [128, 64, 32]):
            """Initialize gate agent network.

            Args:
                state_dim: Input state dimension
                hidden_dims: List of hidden layer dimensions
            """
            super().__init__()

            layers = []
            input_dim = state_dim

            # Build hidden layers
            for hidden_dim in hidden_dims:
                layers.append(nn.Linear(input_dim, hidden_dim))
                layers.append(nn.ReLU())
                layers.append(nn.Dropout(0.2))
                input_dim = hidden_dim

            # Output layer (binary classification)
            layers.append(nn.Linear(input_dim, 2))

            self.network = nn.Sequential(*layers)

        def forward(self, state: torch.Tensor) -> torch.Tensor:
            """Forward pass.

            Args:
                state: State tensor (batch_size, state_dim)

            Returns:
                Logits for skip/pass (batch_size, 2)
            """
            return self.network(state)

        def predict(self, state: np.ndarray) -> int:
            """Predict action for single state.

            Args:
                state: State array (state_dim,)

            Returns:
                Action: 0 = skip, 1 = pass
            """
            self.eval()
            with torch.no_grad():
                state_tensor = torch.FloatTensor(state).unsqueeze(0)
                logits = self.forward(state_tensor)
                action = torch.argmax(logits, dim=1).item()
            return action


    class PortfolioAgentNetwork(nn.Module):
        """Neural network for Portfolio Agent.

        Input: Candidate + LLM + Portfolio context (30 dims from state encoder)
        Output: Position size fraction [0.0, 1.0]
        """

        def __init__(self, state_dim: int = 30, hidden_dims: list = [128, 64, 32]):
            """Initialize portfolio agent network.

            Args:
                state_dim: Input state dimension
                hidden_dims: List of hidden layer dimensions
            """
            super().__init__()

            layers = []
            input_dim = state_dim

            # Build hidden layers
            for hidden_dim in hidden_dims:
                layers.append(nn.Linear(input_dim, hidden_dim))
                layers.append(nn.ReLU())
                layers.append(nn.Dropout(0.2))
                input_dim = hidden_dim

            # Output layer (single value with sigmoid for [0, 1] range)
            layers.append(nn.Linear(input_dim, 1))
            layers.append(nn.Sigmoid())

            self.network = nn.Sequential(*layers)

        def forward(self, state: torch.Tensor) -> torch.Tensor:
            """Forward pass.

            Args:
                state: State tensor (batch_size, state_dim)

            Returns:
                Position size fractions (batch_size, 1) in [0.0, 1.0]
            """
            return self.network(state)

        def predict(self, state: np.ndarray) -> float:
            """Predict position size for single state.

            Args:
                state: State array (state_dim,)

            Returns:
                Position size fraction [0.0, 1.0]
            """
            self.eval()
            with torch.no_grad():
                state_tensor = torch.FloatTensor(state).unsqueeze(0)
                size_fraction = self.forward(state_tensor).item()
            return size_fraction


    class MetaLearnerAgentNetwork(nn.Module):
        """Neural network for Meta-Learner Agent.

        Input: Candidate + LLM + History context (38 dims from state encoder)
        Output: Action (0=agree, 1=override_to_skip, 2=override_to_take)
        """

        def __init__(self, state_dim: int = 38, hidden_dims: list = [128, 64, 32]):
            """Initialize meta-learner agent network.

            Args:
                state_dim: Input state dimension
                hidden_dims: List of hidden layer dimensions
            """
            super().__init__()

            layers = []
            input_dim = state_dim

            # Build hidden layers
            for hidden_dim in hidden_dims:
                layers.append(nn.Linear(input_dim, hidden_dim))
                layers.append(nn.ReLU())
                layers.append(nn.Dropout(0.2))
                input_dim = hidden_dim

            # Output layer (3-class classification)
            layers.append(nn.Linear(input_dim, 3))

            self.network = nn.Sequential(*layers)

        def forward(self, state: torch.Tensor) -> torch.Tensor:
            """Forward pass.

            Args:
                state: State tensor (batch_size, state_dim)

            Returns:
                Logits for 3 actions (batch_size, 3)
            """
            return self.network(state)

        def predict(self, state: np.ndarray) -> int:
            """Predict action for single state.

            Args:
                state: State array (state_dim,)

            Returns:
                Action: 0=agree, 1=override_to_skip, 2=override_to_take
            """
            self.eval()
            with torch.no_grad():
                state_tensor = torch.FloatTensor(state).unsqueeze(0)
                logits = self.forward(state_tensor)
                action = torch.argmax(logits, dim=1).item()
            return action


def create_agent_network(agent_name: str, **kwargs):
    """Factory function to create agent networks.

    Args:
        agent_name: Agent name ("gate", "portfolio", "meta_learner")
        **kwargs: Additional arguments for network construction

    Returns:
        Neural network instance

    Raises:
        ValueError: If agent_name is invalid
        RuntimeError: If PyTorch not available
    """
    if not TORCH_AVAILABLE:
        raise RuntimeError("PyTorch not available. Install with: pip install torch")

    if agent_name == "gate":
        return GateAgentNetwork(**kwargs)
    elif agent_name == "portfolio":
        return PortfolioAgentNetwork(**kwargs)
    elif agent_name == "meta_learner":
        return MetaLearnerAgentNetwork(**kwargs)
    else:
        raise ValueError(f"Unknown agent name: {agent_name}")
