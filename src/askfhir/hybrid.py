"""Hybrid retrieval: Reciprocal Rank Fusion of BM25 and vector rankings.

RRF score for a chunk = sum over rankers of 1 / (k + rank), with rank
1-based and k = 60 (the value from the original RRF paper, Cormack et al.).
RRF needs no score normalization, which matters here because BM25 scores and
cosine similarities live on incomparable scales.
"""

from __future__ import annotations

RRF_K = 60


def reciprocal_rank_fusion(
    rankings: list[list[int]], k: int = RRF_K, top_n: int = 20
) -> list[tuple[int, float]]:
    """Fuse ranked lists of chunk positions into one ranked list.

    Returns [(chunk_position, fused_score)] sorted by score desc, ties by
    lower chunk position.
    """
    fused: dict[int, float] = {}
    for ranking in rankings:
        for rank, pos in enumerate(ranking, start=1):
            fused[pos] = fused.get(pos, 0.0) + 1.0 / (k + rank)
    ordered = sorted(fused.items(), key=lambda kv: (-kv[1], kv[0]))
    return ordered[:top_n]
