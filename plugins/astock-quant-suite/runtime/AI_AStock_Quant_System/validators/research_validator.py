from __future__ import annotations

from functools import reduce
from operator import mul


class ResearchValidator:
    def validate_search_space(self, search_space: dict, max_experiments: int = 200) -> list[str]:
        size = reduce(mul, [len(v) for v in search_space.values()], 1) if search_space else 0
        issues = []
        if size == 0:
            issues.append("搜索空间为空")
        if size > max_experiments:
            issues.append(f"实验数量过大：{size} > {max_experiments}")
        return issues

