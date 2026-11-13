import math

from askfhir.hybrid import reciprocal_rank_fusion


def test_rrf_math():
    # chunk 1 is rank2 in list A and rank1 in list B
    fused = dict(reciprocal_rank_fusion([[0, 1, 2], [2, 1]], k=60))
    assert math.isclose(fused[1], 1 / 62 + 1 / 62, rel_tol=1e-9)
    assert math.isclose(fused[0], 1 / 61, rel_tol=1e-9)
    assert math.isclose(fused[2], 1 / 63 + 1 / 61, rel_tol=1e-9)


def test_rrf_agreement_wins_and_topn():
    fused = reciprocal_rank_fusion([[5, 6, 7], [6, 5, 8]], k=60, top_n=2)
    positions = [p for p, _ in fused]
    assert set(positions) == {5, 6}  # both lists agree on 5 and 6
    assert len(fused) == 2


def test_rrf_deterministic_ties():
    a = reciprocal_rank_fusion([[0, 1], [1, 0]], k=60)
    b = reciprocal_rank_fusion([[0, 1], [1, 0]], k=60)
    assert a == b
    # equal scores -> lower position first
    assert a[0][0] == 0
