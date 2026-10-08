"""Deterministic per-player option shuffling."""

from __future__ import annotations

import random


def shuffle_options(
    options: list[str],
    correct_indices: list[int],
    *,
    seed: int | None = None,
) -> tuple[list[str], list[int], list[int]]:
    """Return (shuffled_options, new_correct, order).

    `order[new_idx] = old_idx` so hosts can map answers back.
    """
    order = list(range(len(options)))
    rng = random.Random(seed)
    rng.shuffle(order)
    shuffled = [options[i] for i in order]
    remap = {old: new for new, old in enumerate(order)}
    new_correct = sorted({remap[i] for i in correct_indices if i in remap})
    if not new_correct:
        new_correct = [0]
    return shuffled, new_correct, order


def unshuffle_index(shuffled_idx: int, order: list[int]) -> int:
    """Map a player-facing index back to canonical."""
    if 0 <= shuffled_idx < len(order):
        return order[shuffled_idx]
    return shuffled_idx
