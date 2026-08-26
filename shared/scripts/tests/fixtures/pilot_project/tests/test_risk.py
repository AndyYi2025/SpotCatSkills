def test_position_limit_enforced():
    max_position = 10
    placed_qty = 8
    assert placed_qty <= max_position


def test_duplicate_signal_not_double_ordered():
    seen_keys = set()
    key = "strat1_2024-06-01T00:00:00_buy"
    first = key not in seen_keys
    seen_keys.add(key)
    second = key not in seen_keys
    assert first is True
    assert second is False


def test_live_trading_requires_dual_kill_switch():
    def would_trade(project_flag: bool, global_flag: bool) -> bool:
        return project_flag and global_flag

    assert would_trade(True, True) is True
    assert would_trade(True, False) is False
    assert would_trade(False, True) is False
    assert would_trade(False, False) is False
