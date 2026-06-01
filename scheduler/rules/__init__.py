"""Scheduling rules package — auto-registers all built-in rules."""
from .base import RuleRegistry
from .individual_wait import IndividualWaitRule
from .operator_fairness import OperatorFairnessRule
from .throughput import ThroughputRule


def create_default_registry() -> RuleRegistry:
    """Create a RuleRegistry with all built-in soft rules registered."""
    registry = RuleRegistry()
    registry.register(IndividualWaitRule())
    registry.register(OperatorFairnessRule())
    registry.register(ThroughputRule())
    return registry
