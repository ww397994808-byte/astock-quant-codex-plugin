from __future__ import annotations

import random


BUY_SETS = [
    [0.004, 0.008, 0.014, 0.022],
    [0.006, 0.012, 0.020, 0.032],
    [0.0068, 0.0115, 0.0170, 0.0235],
    [0.008, 0.015, 0.025, 0.040],
]

SELL_SETS = [
    [0.006, 0.011, 0.018, 0.028],
    [0.008, 0.015, 0.025, 0.038],
    [0.010, 0.018, 0.030, 0.045],
    [0.0125, 0.0210, 0.0305, 0.0410],
]

WEIGHTS = [
    [0.25, 0.25, 0.25, 0.25],
    [0.50, 0.28, 0.12, 0.10],
    [0.20, 0.25, 0.25, 0.30],
    [0.15, 0.20, 0.30, 0.35],
]

FILTERS = [
    {"mode": "none"},
    {"mode": "long_ma_guard", "long_ma": 8, "slope_days": 3, "below_long_mult": 0.5, "down_slope_mult": 0.0},
    {"mode": "long_ma_guard", "long_ma": 10, "slope_days": 3, "below_long_mult": 0.5, "down_slope_mult": 0.0},
    {"mode": "long_ma_guard", "long_ma": 10, "slope_days": 5, "below_long_mult": 0.5, "down_slope_mult": 0.0},
    {"mode": "long_ma_guard", "long_ma": 20, "slope_days": 5, "below_long_mult": 0.5, "down_slope_mult": 0.25},
]

SEEDS = [
    {
        "ma_period": 2,
        "refresh_minutes": 10,
        "atr_mult": 1.3,
        "buy_discounts": [0.006, 0.012, 0.020, 0.032],
        "sell_premiums": [0.010, 0.018, 0.030, 0.045],
        "buy_weights": [0.25, 0.25, 0.25, 0.25],
        "cash_slices": 5,
        "position_slices": 3,
        "initial_position_fraction": 0.75,
        "filter": {"mode": "long_ma_guard", "long_ma": 10, "slope_days": 3, "below_long_mult": 0.5, "down_slope_mult": 0.0},
    },
    {
        "ma_period": 5,
        "refresh_minutes": 10,
        "atr_mult": 0.55,
        "buy_discounts": [0.0068, 0.0115, 0.0170, 0.0235],
        "sell_premiums": [0.006, 0.011, 0.018, 0.028],
        "buy_weights": [0.15, 0.20, 0.30, 0.35],
        "cash_slices": 2,
        "position_slices": 5,
        "initial_position_fraction": 1.0,
        "filter": {"mode": "none"},
    },
    {
        "ma_period": 5,
        "refresh_minutes": 10,
        "atr_mult": 0.55,
        "buy_discounts": [0.0068, 0.0115, 0.0170, 0.0235],
        "sell_premiums": [0.006, 0.011, 0.018, 0.028],
        "buy_weights": [0.15, 0.20, 0.30, 0.35],
        "cash_slices": 2,
        "position_slices": 5,
        "initial_position_fraction": 1.0,
        "filter": {"mode": "trend_regime", "strong_ma": 15, "strong_slope_days": 5, "weak_ma": 20, "weak_slope_days": 5, "strong_buy_mult": 0.75, "strong_sell_qty_mult": 1.0, "strong_sell_widen": 1.0, "weak_buy_mult": 0.5, "weak_sell_qty_mult": 2.0},
    },
]


def make_random_params() -> dict:
    return {
        "ma_period": random.choice([2, 3, 4, 5, 6]),
        "refresh_minutes": random.choice([10, 20]),
        "atr_mult": random.choice([0.55, 0.7, 0.85, 1.0, 1.15, 1.3, 1.5]),
        "buy_discounts": random.choice(BUY_SETS),
        "sell_premiums": random.choice(SELL_SETS),
        "buy_weights": random.choice(WEIGHTS),
        "cash_slices": random.choice([2, 3, 4, 5, 6]),
        "position_slices": random.choice([2, 3, 4, 5, 6]),
        "initial_position_fraction": random.choice([0.5, 0.75, 1.0]),
        "filter": random.choice(FILTERS),
    }


def make_param_pool(n_random: int = 297, seed: int = 20260625) -> list[dict]:
    random.seed(seed)
    live_seed = {
        "ma_period": 3,
        "refresh_minutes": 10,
        "atr_mult": 1.0,
        "buy_discounts": [0.0068, 0.0115, 0.0170, 0.0235],
        "sell_premiums": [0.0125, 0.0210, 0.0305, 0.0410],
        "buy_weights": [0.50, 0.28, 0.12, 0.10],
        "cash_slices": 4,
        "position_slices": 4,
        "initial_position_fraction": 1.0,
        "filter": {"mode": "none"},
    }
    live_variants = []
    for ma_period in [2, 3, 4, 5]:
        for atr_mult in [0.7, 0.85, 1.0, 1.15, 1.3]:
            for cash_slices in [2, 3, 4]:
                row = dict(live_seed)
                row.update({"ma_period": ma_period, "atr_mult": atr_mult, "cash_slices": cash_slices})
                live_variants.append(row)
    pool = [dict(seed_row) for seed_row in SEEDS] + [live_seed] + live_variants
    pool.extend(make_random_params() for _ in range(n_random))
    seen = set()
    unique = []
    for row in pool:
        key = repr(row)
        if key not in seen:
            seen.add(key)
            unique.append(row)
    return unique
