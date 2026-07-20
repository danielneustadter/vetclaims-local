"""§4.25/§4.26 math against the regulation's own published examples."""

from app.analysis.rating_math import (Rating, combined_rating,
                                      combined_rating_bilateral,
                                      combined_value, what_if)


def test_425_published_examples():
    # 38 CFR 4.25(a): "60 and 30 → combined value 72 → converted to 70"
    assert round(combined_value([60, 30])) == 72
    assert combined_rating([60, 30]) == 70
    # "40 and 20 → 52 → 50"
    assert combined_rating([40, 20]) == 50
    # three disabilities example: 40, 30, 20 → 66.4 → 70? Actually 40+30 → 58;
    # 58 with 20 → 66.4 → rounds to 70? 66.4 → nearest 10 is 70 (66.4 ≥ 65).
    assert combined_rating([40, 30, 20]) == 70


def test_rounding_edges():
    assert combined_rating([10]) == 10
    assert combined_rating([10, 10]) == 20   # 19 → 20 (15+ rounds up)
    assert combined_rating([20, 10]) == 30   # 28 → 30
    assert combined_rating([10, 10, 10]) == 30  # 27.1 → 30
    assert combined_rating([]) == 0
    assert combined_rating([0, 0]) == 0
    assert combined_rating([100]) == 100


def test_426_bilateral_example():
    # §4.26(a) example: 30% left thigh + 20% right thigh:
    # combined 44, bilateral factor 4.4 → 48.4 treated as one 48.4 rating.
    r = [Rating(30, "legs"), Rating(20, "legs")]
    assert combined_rating_bilateral(r) == 50  # 48.4 alone rounds to 50

    # with an additional 20% back (not bilateral):
    # 48.4 combined with 20 → 58.7 → 60
    r2 = r + [Rating(20)]
    assert combined_rating_bilateral(r2) == 60


def test_bilateral_needs_two():
    # single paired-limb rating: no factor applied
    assert combined_rating_bilateral([Rating(30, "legs")]) == 30


def test_what_if():
    current = [Rating(10, label="tinnitus"), Rating(10, label="knee")]
    out = what_if(current, Rating(50, label="PTSD"))
    assert out["before"] == 20
    # 50 + 10 + 10: 50→55→59.5 → 60
    assert out["after"] == 60
    assert out["delta"] == 40
