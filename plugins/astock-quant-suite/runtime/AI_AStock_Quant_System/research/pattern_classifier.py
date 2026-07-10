from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PatternClassification:
    pattern: str
    confidence: float
    blocker: bool = False
    blocker_note: str = ""
    matched_keywords: list[str] | None = None


class PatternClassifier:
    RULES = [
        ("pair_trading", ["配对", "套利", "A/H价差"], True, "A股第一版不支持裸卖空或融资融券；配对/套利方向只输出 BLOCKER，不进入推荐。"),
        ("event_driven", ["财报", "分红", "公告", "事件"], True, "事件驱动需要稳定事件数据源和可复核事件字段；第一版只输出 BLOCKER，不进入推荐。"),
        ("grid", ["网格", "分层买卖", "区间震荡"], False, ""),
        ("swing", ["布林低吸", "回撤买入", "波段", "反弹卖出"], False, ""),
        ("swing", ["周线", "1w", "weekly"], False, ""),
        ("swing", ["1h", "1小时", "10分钟", "10min"], False, ""),
        ("timing", ["均线", "MACD", "趋势", "择时"], False, ""),
        ("stock_selection", ["选股", "高股息", "低波动", "因子", "TopN", "topn"], False, ""),
        ("rotation", ["轮动", "切换", "强弱", "ETF轮动", "行业轮动"], False, ""),
        ("portfolio", ["组合", "再平衡", "等权", "权重"], False, ""),
    ]

    def classify(self, direction: str) -> PatternClassification:
        text = direction.lower()
        for pattern, keywords, blocker, note in self.RULES:
            matched = [kw for kw in keywords if kw.lower() in text]
            if matched:
                return PatternClassification(pattern=pattern, confidence=min(0.95, 0.55 + 0.1 * len(matched)), blocker=blocker, blocker_note=note, matched_keywords=matched)
        return PatternClassification(pattern="timing", confidence=0.35, blocker=False, matched_keywords=[])
