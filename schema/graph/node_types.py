"""Knowledge graph node types for ArcadeDB vertex types.

Defines the six base node types used in the Agent Operations knowledge graph:
- ProductStructure: Structural discoveries about the product (slow decay)
- DecisionRecord: Architectural and design decisions (very slow decay)
- InvestigationFinding: Findings from investigations (medium decay)
- CompetitorCapability: Observed competitor capabilities (fast decay)
- CustomerTheme: Aggregated customer themes (medium-fast decay)
- CustomerSignal: Individual customer signals (very fast decay)

Each node type carries confidence that decays over time. Nodes below 0.3
confidence are flagged for revalidation.
"""

from dataclasses import dataclass
from datetime import datetime

DECAY_RATES: dict[str, float] = {
    "ProductStructure": 0.001,
    "DecisionRecord": 0.0001,
    "InvestigationFinding": 0.005,
    "CompetitorCapability": 0.01,
    "CustomerTheme": 0.008,
    "CustomerSignal": 0.1,
}

REVALIDATION_THRESHOLD = 0.3


@dataclass
class GraphNode:
    """Base knowledge graph node with confidence decay."""

    node_id: str
    node_type: str
    confidence: float
    initial_confidence: float
    decay_rate: float
    last_reinforced: datetime
    revalidation_required: bool

    def __post_init__(self) -> None:
        if self.node_type not in DECAY_RATES:
            raise ValueError(
                f"node_type must be one of {list(DECAY_RATES.keys())}, got '{self.node_type}'"
            )
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0.0, 1.0], got {self.confidence}")
        if not 0.0 <= self.initial_confidence <= 1.0:
            raise ValueError(
                f"initial_confidence must be in [0.0, 1.0], got {self.initial_confidence}"
            )


@dataclass
class ProductStructure(GraphNode):
    """Structural discovery about the product. Decay rate: 0.001/day."""

    def __post_init__(self) -> None:
        self.node_type = "ProductStructure"
        self.decay_rate = DECAY_RATES["ProductStructure"]
        super().__post_init__()


@dataclass
class DecisionRecord(GraphNode):
    """Architectural or design decision. Decay rate: 0.0001/day."""

    def __post_init__(self) -> None:
        self.node_type = "DecisionRecord"
        self.decay_rate = DECAY_RATES["DecisionRecord"]
        super().__post_init__()


@dataclass
class InvestigationFinding(GraphNode):
    """Finding from an investigation. Decay rate: 0.005/day."""

    def __post_init__(self) -> None:
        self.node_type = "InvestigationFinding"
        self.decay_rate = DECAY_RATES["InvestigationFinding"]
        super().__post_init__()


@dataclass
class CompetitorCapability(GraphNode):
    """Observed competitor capability. Decay rate: 0.01/day."""

    def __post_init__(self) -> None:
        self.node_type = "CompetitorCapability"
        self.decay_rate = DECAY_RATES["CompetitorCapability"]
        super().__post_init__()


@dataclass
class CustomerTheme(GraphNode):
    """Aggregated customer theme. Decay rate: 0.008/day."""

    def __post_init__(self) -> None:
        self.node_type = "CustomerTheme"
        self.decay_rate = DECAY_RATES["CustomerTheme"]
        super().__post_init__()


@dataclass
class CustomerSignal(GraphNode):
    """Individual customer signal. Decay rate: 0.1/day."""

    def __post_init__(self) -> None:
        self.node_type = "CustomerSignal"
        self.decay_rate = DECAY_RATES["CustomerSignal"]
        super().__post_init__()


def calculate_current_confidence(node: GraphNode, current_time: datetime) -> float:
    """Calculate current confidence after decay.

    Applies exponential decay based on the node's decay rate and the time
    elapsed since last reinforcement. Flags the node for revalidation if
    confidence drops below 0.3.

    Args:
        node: The graph node to calculate confidence for
        current_time: The current time to calculate decay to

    Returns:
        The current confidence value after decay
    """
    elapsed_days = (current_time - node.last_reinforced).total_seconds() / 86400.0
    if elapsed_days < 0:
        elapsed_days = 0.0
    current_confidence: float = node.confidence * (1.0 - node.decay_rate) ** elapsed_days
    if current_confidence < REVALIDATION_THRESHOLD:
        node.revalidation_required = True
    return current_confidence
