from audit.future_leak_checker import FutureLeakChecker


def test_future_leak_checker_detects_shift_minus_one():
    report = FutureLeakChecker().check_code_text("df['x'] = close.shift(-1)")
    assert report["status"] == "INVALID"


def test_future_leak_checker_detects_iloc_i_plus_one():
    report = FutureLeakChecker().check_code_text("next_close = data.iloc[i+1]['close']")
    assert report["status"] == "INVALID"


def test_future_leak_checker_detects_centered_rolling():
    report = FutureLeakChecker().check_code_text("signal = close.rolling(20, center=True).mean()")
    assert report["status"] == "INVALID"


def test_future_leak_checker_detects_negative_pct_change():
    report = FutureLeakChecker().check_code_text("future_ret = close.pct_change(periods=-1)")
    assert report["status"] == "INVALID"
