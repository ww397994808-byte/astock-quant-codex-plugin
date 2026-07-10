"""Core5 high-dividend relative-strength grid research package."""

from .config import CORE5, FixedRule, default_rule
from .walk_forward import run_fixed_rule_start_check

__all__ = ["CORE5", "FixedRule", "default_rule", "run_fixed_rule_start_check"]
