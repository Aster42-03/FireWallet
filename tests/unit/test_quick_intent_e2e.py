"""
Quick Intent Category Classification Bug Fix E2E Test Suite (R4 / BUG-009)
=============================================================================
Comprehensive 4-Tier test suite verifying that Quick Intent spending intents
are accurately classified into the canonical 7-category taxonomy:
    `groceries`, `transit`, `utilities`, `entertainment`, `gifts`,
    `eating_out` (or `dining_out`), `emergency`
and that old scaffolding artifacts (`medical_emergency`, `savings_violation`,
`"food"` keyword collisions) are completely resolved.

Tiers:
- Tier 1: Feature Coverage (>=5 tests: groceries, transit, utilities, entertainment, gifts, dining, emergency)
- Tier 2: Boundary & Corner Cases (>=5 tests: "food" token disambiguation, scaffolding removal, edge cases)
- Tier 3: Cross-Feature Combinations (emergency flags, zero-delay metadata, luxury splurge rejection)
- Tier 4: Real-World Scenarios (multi-intent daily financial journey with zero scaffolding artifacts)
"""

import pytest
from app.agents.shared.llm_client import LLMClient
from app.agents.rag import distill_short_tag, is_genuine_emergency


CANONICAL_CATEGORIES = {
    "groceries",
    "transit",
    "utilities",
    "entertainment",
    "gifts",
    "eating_out",
    "dining_out",
    "emergency",
}

DISALLOWED_SCAFFOLDING_LABELS = {
    "medical_emergency",
    "savings_violation",
    "other",
    "general",
}


@pytest.fixture
def classifier():
    """Provides the deterministic heuristic classifier from LLMClient."""
    client = LLMClient()
    return client._classify_text_heuristically


# =====================================================================
# TIER 1: FEATURE COVERAGE (All Core Categories)
# =====================================================================

@pytest.mark.unit
def test_tier1_classify_groceries_supermarket(classifier):
    """Tier 1: Verify supermarket groceries intent maps to 'groceries'."""
    res = classifier("Weekly groceries at Safeway buying vegetables and bread", "Safeway")
    assert res["category"] == "groceries"
    assert res["necessity"] == "daily_living"
    assert res["recommended_bucket"] == "daily"
    assert res["is_emergency"] is False


@pytest.mark.unit
def test_tier1_classify_transit_subway(classifier):
    """Tier 1: Verify transit and public transit commute maps to 'transit'."""
    res = classifier("Metro subway pass recharge for weekly commute", "MTA Transit")
    assert res["category"] == "transit"
    assert res["necessity"] == "daily_living"
    assert res["recommended_bucket"] == "daily"
    assert res["is_emergency"] is False


@pytest.mark.unit
def test_tier1_classify_utilities_electric_bill(classifier):
    """Tier 1: Verify recurring utility bills map to 'utilities'."""
    res = classifier("Monthly electric power utility bill", "ConEd")
    assert res["category"] == "utilities"
    assert res["necessity"] == "bill"
    assert res["recommended_bucket"] == "bills"
    assert res["is_emergency"] is False


@pytest.mark.unit
def test_tier1_classify_entertainment_concert(classifier):
    """Tier 1: Verify discretionary concerts and events map to 'entertainment'."""
    res = classifier("Two tickets for indie band rock concert", "Ticketmaster")
    assert res["category"] == "entertainment"
    assert res["necessity"] == "freedom"
    assert res["recommended_bucket"] == "freedom"
    assert res["is_emergency"] is False


@pytest.mark.unit
def test_tier1_classify_gifts_birthday(classifier):
    """Tier 1: Verify gifts for family/friends map to 'gifts'."""
    res = classifier("Picking up a birthday gift for mom", "Amazon")
    assert res["category"] == "gifts"
    assert res["necessity"] == "freedom"
    assert res["recommended_bucket"] == "freedom"
    assert res["is_emergency"] is False


@pytest.mark.unit
def test_tier1_classify_eating_out_restaurant(classifier):
    """Tier 1: Verify dining out at restaurants maps to 'eating_out' or 'dining_out'."""
    res = classifier("Dinner and cocktails with friends at Italian bistro", "Luigi's Bistro")
    assert res["category"] in ("eating_out", "dining_out")
    assert res["necessity"] == "freedom"
    assert res["recommended_bucket"] == "freedom"
    assert res["is_emergency"] is False


@pytest.mark.unit
def test_tier1_classify_emergency_medical(classifier):
    """Tier 1: Verify genuine emergency medical expense maps to 'emergency'."""
    res = classifier("Urgent hospital emergency room copay for broken wrist", "General Hospital")
    assert res["category"] == "emergency"
    assert res["is_emergency"] is True
    assert "valid_emergency" in res.get("flags", [])


# =====================================================================
# TIER 2: BOUNDARY & CORNER CASES (Scaffolding Cleanup & Disambiguation)
# =====================================================================

@pytest.mark.unit
def test_tier2_food_token_disambiguation_dining_not_groceries(classifier):
    """
    Tier 2: Disambiguate 'food' token.
    'Thai food takeout' must classify as dining/eating_out, NOT groceries.
    """
    res = classifier("Ordering spicy Thai food takeout for dinner", "Thai Spice")
    assert res["category"] in ("eating_out", "dining_out"), (
        f"Expected eating_out/dining_out but got '{res['category']}'. "
        "The generic 'food' keyword must not swallow restaurant takeout as groceries."
    )
    assert res["category"] != "groceries"


@pytest.mark.unit
def test_tier2_food_token_fast_food(classifier):
    """
    Tier 2: Fast food burger orders must classify as eating_out, not groceries.
    """
    res = classifier("Grabbing fast food burger and fries for lunch", "Five Guys")
    assert res["category"] in ("eating_out", "dining_out")
    assert res["category"] != "groceries"


@pytest.mark.unit
def test_tier2_medical_emergency_scaffolding_removed(classifier):
    """
    Tier 2: Verify that 'medical_emergency' scaffolding artifact is removed.
    The category must be the canonical 'emergency'.
    """
    res = classifier("Emergency medical clinic visit and prescription", "City Urgent Care")
    assert res["category"] == "emergency", (
        f"Scaffolding artifact detected: category is '{res['category']}', "
        "expected canonical 'emergency'."
    )
    assert res["category"] not in DISALLOWED_SCAFFOLDING_LABELS


@pytest.mark.unit
def test_tier2_savings_violation_scaffolding_removed(classifier):
    """
    Tier 2: Attempting to spend from locked savings must NOT return the
    scaffolding label 'savings_violation'. It must return a recognized category.
    """
    res = classifier("Spend from vault to buy a luxury winter designer coat", "Nordstrom")
    assert res["category"] not in DISALLOWED_SCAFFOLDING_LABELS, (
        f"Scaffolding artifact detected: category is '{res['category']}'."
    )
    assert res["category"] in CANONICAL_CATEGORIES


@pytest.mark.unit
def test_tier2_case_insensitivity_and_punctuation(classifier):
    """
    Tier 2: Utterance casing and extreme punctuation should not disrupt classification.
    """
    res_caps = classifier("GROCERIES AT SAFEWAY!!! $$$", "SAFEWAY")
    assert res_caps["category"] == "groceries"

    res_mixed = classifier("uRgEnT eR hOsPiTaL CoPaY!!!", "HOSPITAL")
    assert res_mixed["category"] == "emergency"
    assert res_mixed["is_emergency"] is True


@pytest.mark.unit
def test_tier2_minimal_and_ambiguous_utterance(classifier):
    """
    Tier 2: Very short or minimal merchant input should produce a valid fallback category.
    """
    res = classifier("coffee", "Starbucks")
    assert res["category"] in CANONICAL_CATEGORIES
    assert res["category"] not in DISALLOWED_SCAFFOLDING_LABELS


# =====================================================================
# TIER 3: CROSS-FEATURE COMBINATIONS
# =====================================================================

@pytest.mark.unit
def test_tier3_emergency_classification_triggers_zero_cooldown_metadata(classifier):
    """
    Tier 3: Verified emergency classification attaches valid_emergency and zero_cooldown flags.
    """
    res = classifier("Stranded on highway with blown tire needing AAA tow truck", "AAA Towing")
    assert res["is_emergency"] is True
    assert res["category"] == "emergency"
    flags = res.get("flags", [])
    assert "valid_emergency" in flags
    assert "zero_cooldown" in flags


@pytest.mark.unit
def test_tier3_luxury_splurge_with_emergency_phrase_rejected(classifier):
    """
    Tier 3: Luxury spend claiming 'emergency reserves' must be rejected as an emergency.
    """
    res = classifier(
        "I am choosing to spend $150 from my emergency reserves celebrating promotion at a steakhouse",
        "Prime Steakhouse",
    )
    assert res["is_emergency"] is False
    assert res["category"] in ("eating_out", "dining_out", "entertainment")
    assert "valid_emergency" not in res.get("flags", [])


@pytest.mark.unit
def test_tier3_utility_shutoff_classified_as_emergency(classifier):
    """
    Tier 3: Acute utility shutoff notice is classified as genuine emergency.
    """
    res = classifier("Urgent power shutoff notice paying electric company now", "ConEd")
    assert res["is_emergency"] is True
    assert res["category"] == "emergency"


# =====================================================================
# TIER 4: REAL-WORLD SCENARIOS
# =====================================================================

@pytest.mark.unit
def test_tier4_full_day_spending_journey_canonical_taxonomy(classifier):
    """
    Tier 4: Simulate a realistic full day of spending intents.
    Every intent must map strictly into the 7 canonical categories with zero
    lingering scaffolding labels.
    """
    journey = [
        ("Subway swipe to downtown office", "MTA", "transit"),
        ("Takeout lunch at sushi bar", "Wasabi Sushi", ("eating_out", "dining_out")),
        ("Weekly groceries apples bread milk", "Trader Joe's", "groceries"),
        ("Monthly high-speed internet wifi bill", "Verizon", "utilities"),
        ("Movie tickets for Friday premiere", "AMC Theatres", "entertainment"),
        ("Birthday present for best friend", "Gift Boutique", "gifts"),
        ("Late night emergency room prescription copay", "ER Pharmacy", "emergency"),
    ]

    for utterance, merchant, expected_category in journey:
        res = classifier(utterance, merchant)
        cat = res["category"]
        assert cat in CANONICAL_CATEGORIES, (
            f"Utterance '{utterance}' produced non-canonical category '{cat}'"
        )
        assert cat not in DISALLOWED_SCAFFOLDING_LABELS, (
            f"Utterance '{utterance}' produced scaffolding label '{cat}'"
        )
        if isinstance(expected_category, tuple):
            assert cat in expected_category, (
                f"Utterance '{utterance}': expected one of {expected_category}, got '{cat}'"
            )
        else:
            assert cat == expected_category, (
                f"Utterance '{utterance}': expected '{expected_category}', got '{cat}'"
            )
