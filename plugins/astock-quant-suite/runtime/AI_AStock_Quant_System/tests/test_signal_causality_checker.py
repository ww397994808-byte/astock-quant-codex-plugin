from strategy_safety.causality_checker import SignalCausalityChecker


def status(code: str) -> str:
    return SignalCausalityChecker().check_text(code).status


def test_causality_checker_rejects_shift_negative():
    assert status("signal = close.shift(-1) > close") == "INVALID"


def test_causality_checker_rejects_shift_negative_keyword():
    assert status("signal = close.shift(periods=-1) > close") == "INVALID"


def test_causality_checker_rejects_negative_pct_change_and_diff():
    assert status("future_ret = close.pct_change(-1)") == "INVALID"
    assert status("future_delta = close.diff(periods=-1)") == "INVALID"


def test_causality_checker_rejects_centered_rolling():
    assert status("signal = close > close.rolling(20, center=True).mean()") == "INVALID"


def test_causality_checker_rejects_forward_asof_merge():
    assert status("features = df.merge_asof(events, on='date', direction='forward')") == "INVALID"


def test_causality_checker_rejects_rows_index_plus_one():
    code = """
for i in range(len(rows)):
    next_close = rows[i + 1]["close"]
"""
    assert status(code) == "INVALID"


def test_causality_checker_rejects_iloc_plus_one():
    assert status("next_close = df.iloc[i+1]['close']") == "INVALID"


def test_causality_checker_rejects_future_variable_names():
    assert status("future_return = close / open - 1") == "INVALID"


def test_causality_checker_warns_full_sample_mean():
    report = SignalCausalityChecker().check_text("signal = close > close.mean()")
    assert report.status == "VALID"
    assert any(item.severity == "MEDIUM" for item in report.findings)


def test_causality_checker_rejects_external_io():
    assert status("import requests\nx = requests.get('https://example.com')") == "INVALID"


def test_causality_checker_allows_history_window_code():
    code = """
history = rows[-20:]
avg = sum(row["close"] for row in history) / len(history)
signal = rows[-1]["close"] < avg * 0.95
"""
    assert status(code) == "VALID"
