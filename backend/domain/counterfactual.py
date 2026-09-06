
from __future__ import annotations


def build_counterfactual(rank: int, ranked_final_scores: list[tuple[str, float]]) -> str | None:
    if rank != 1 or len(ranked_final_scores) < 2:
        return None
    runner_up_id, runner_up_score = ranked_final_scores[1]
    return f"{runner_up_id} would rank first if this vendor's final score fell below {runner_up_score:.1f}."
