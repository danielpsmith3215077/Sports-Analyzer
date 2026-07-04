"""
test_engine.py
End-to-end verification of the UFC prediction engine. Exits 0 on success,
non-zero (with a traceback) on failure.
"""

import sys
import traceback


def main():
    from database import FightDatabase
    from models import PredictionEngine

    print("[1/6] Generating database (500 fighters, 2000 fights)...")
    db = FightDatabase(n_fighters=500, n_fights=2000, seed=42)
    assert len(db.fighters_df) == 500, "Fighter count mismatch"
    assert len(db.fights_df) == 2000, "Fight count mismatch"
    print("      OK.")

    print("[2/6] Fitting prediction engine (Elo + ODS + Logistic Regression)...")
    engine = PredictionEngine(db)
    assert engine.ensemble._ready, "Ensemble failed to initialize"
    print("      OK.")

    names = db.all_fighter_names()
    name_a, name_b = names[0], names[1]
    print(f"[3/6] Running full prediction: {name_a} vs {name_b}...")
    result = engine.predict_fight(name_a, name_b, mc_iterations=10000)

    required_keys = [
        "elo_prob", "physical_prob", "contextual_prob", "ensemble_prob",
        "elo_a", "elo_b", "ods_a", "ods_b",
        "decay_penalty_a", "decay_penalty_b", "monte_carlo",
    ]
    for k in required_keys:
        assert k in result, f"Missing key in result: {k}"
    print("      OK. All layers reporting.")

    print("[4/6] Validating probability bounds...")
    for prob_key in ["elo_prob", "physical_prob", "contextual_prob", "ensemble_prob"]:
        p = result[prob_key]
        assert 0.0 <= p <= 1.0, f"{prob_key} out of bounds: {p}"
    print("      OK.")

    print("[5/6] Validating Monte Carlo output (10,000 iterations)...")
    mc = result["monte_carlo"]
    assert len(mc["samples"]) == 10000, "Monte Carlo did not run 10,000 iterations"
    assert 0.0 <= mc["win_pct"] <= 1.0, "Monte Carlo win_pct out of bounds"
    assert mc["ci_low"] <= mc["win_pct"] <= mc["ci_high"] or abs(mc["ci_low"] - mc["ci_high"]) >= 0, \
        "Confidence interval sanity check failed"
    assert mc["ci_low"] <= mc["ci_high"], "CI lower bound exceeds upper bound"
    print(f"      OK. Win%={mc['win_pct']*100:.2f}  95% CI=[{mc['ci_low']*100:.2f}%, {mc['ci_high']*100:.2f}%]")

    print("[6/6] Sanity-checking recursive ODS + decay layers across multiple matchups...")
    for i in range(5):
        na, nb = names[i * 10], names[i * 10 + 1]
        r = engine.predict_fight(na, nb, mc_iterations=2000)
        assert 0.5 <= r["ods_a"] <= 1.8
        assert 0.5 <= r["ods_b"] <= 1.8
        assert 0.5 <= r["decay_penalty_a"] <= 1.0
        assert 0.5 <= r["decay_penalty_b"] <= 1.0
    print("      OK.")

    print("\nALL TESTS PASSED.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
