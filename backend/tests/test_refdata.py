from app import refdata


def test_dc_overrides():
    cases = {
        "Tinnitus, noise-induced": "6260",
        "Chronic rhinitis, suspect airborne-hazard related": "6522",
        "Post-Traumatic Stress Disorder (PTSD)": "9411",
        "Low back pain": "5237",
        "Obstructive sleep apnea (aggravation)": "6847",
        "Right knee medial meniscus strain": "5257",
        "Hypertension": "7101",
    }
    for name, expected_dc in cases.items():
        matched = refdata.match_diagnostic_code(name)
        assert matched, f"no match for {name!r}"
        assert matched[0] == expected_dc, \
            f"{name!r} → {matched[0]} ({matched[1]['name']}), expected {expected_dc}"


def test_schedule_loaded():
    schedule = refdata.rating_schedule()
    assert len(schedule) > 500
    assert schedule["6260"]["tiers"][0]["percent"] == 10
    assert [t["percent"] for t in schedule["9411"]["tiers"]] == [100, 70, 50, 30, 10, 0]


def test_dbq_lookup():
    assert refdata.find_dbq("Tinnitus")["dbq"].startswith("Hearing Loss")
    assert refdata.find_dbq("completely unknown thing") is None
