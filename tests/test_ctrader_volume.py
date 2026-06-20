"""Conversion lots → volume protocole cTrader (logique critique, testée sans broker)."""

from __future__ import annotations

import pytest

from copybot.execution.brokers.ctrader_volume import lots_to_volume

# EURUSD standard : 1 lot = 100 000 EUR → lotSize = 10 000 000 (échelle ×100).
EUR = dict(lot_size=10_000_000, min_volume=100_000, max_volume=20_000_000_000, step_volume=100_000)


def test_one_lot_eurusd() -> None:
    # Exemple officiel : 1 lot → volume 10 000 000.
    assert lots_to_volume(1.0, **EUR) == 10_000_000


def test_micro_lot() -> None:
    # 0.01 lot → 100 000.
    assert lots_to_volume(0.01, **EUR) == 100_000


def test_below_min_is_clamped() -> None:
    # 0.0001 lot = 1 000 < min → relevé au minimum.
    assert lots_to_volume(0.0001, **EUR) == 100_000


def test_aligned_on_step() -> None:
    # 0.015 lot = 150 000 → aligné vers le bas sur le pas (100 000) depuis le min.
    assert lots_to_volume(0.015, **EUR) == 100_000


def test_above_max_raises() -> None:
    with pytest.raises(ValueError):
        lots_to_volume(10_000.0, **EUR)


def test_non_positive_raises() -> None:
    with pytest.raises(ValueError):
        lots_to_volume(0, lot_size=10_000_000)
