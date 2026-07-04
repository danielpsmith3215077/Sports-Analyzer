"""
models.py
Implements the six-layer UFC prediction engine:
  Layer 1: Recursive Elo w/ Opponent Difficulty Score (ODS), 3-degree cascade
  Layer 2: Logistic Regression on physical trait discrepancies
  Layer 3: Contextual MMA performance stats (scaled by ODS)
  Layer 4: Weighted ensemble (40% Elo / 35% Contextual / 25% Physical)
  Layer 5: Wear-and-tear decay system (split-decision penalty)
  Layer 6: Monte Carlo simulator (10,000 iterations, Gaussian, 95% CI)
"""

import math
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

STANCE_ENCODING = {"Orthodox": 0, "Southpaw": 1, "Switch": 2}


# ---------------------------------------------------------------------------
# LAYER 1: Recursive Elo + Opponent Difficulty Score
# ---------------------------------------------------------------------------
class RecursiveEloEngine:
    """
    Time-ordered Elo rating system. Each fighter's Elo gain/loss for a fight
    is multiplied by the Opponent Difficulty Score (ODS) of the opponent they
    just faced. ODS is computed recursively by cascading through the
    opponent's own fight history up to 3 degrees of separation, averaging
    the Elo strength found at each layer of opponents.
    """

    def __init__(self, database, k_factor=32, base_elo=1500.0, max_recursion_opponents=5):
        self.db = database
        self.k = k_factor
        self.base_elo = base_elo
        self.max_recursion_opponents = max_recursion_opponents
        self.elo = {fid: base_elo for fid in self.db.fighters_df["fighter_id"]}
        self.ods_cache = {}
        self._final_ods = {}

    def _expected(self, r_a, r_b):
        return 1.0 / (1.0 + 10 ** ((r_b - r_a) / 400.0))

    def _opponent_ids_before(self, fighter_id, cutoff_fight_id):
        opps = []
        for row in self.db.get_history(fighter_id):
            if row["fight_id"] >= cutoff_fight_id:
                continue
            opp = row["loser_id"] if row["winner_id"] == fighter_id else row["winner_id"]
            opps.append(opp)
        return opps[-self.max_recursion_opponents:]

    def _recursive_strength(self, fighter_id, cutoff_fight_id, depth, visited):
        """Recursively cascades through opponents' opponents up to `depth`
        levels, returning an Elo-scale strength estimate."""
        if depth == 0:
            return self.elo.get(fighter_id, self.base_elo)

        opp_ids = [o for o in self._opponent_ids_before(fighter_id, cutoff_fight_id)
                   if o not in visited]
        if not opp_ids:
            return self.elo.get(fighter_id, self.base_elo)

        next_visited = visited | {fighter_id}
        scores = [
            self._recursive_strength(o, cutoff_fight_id, depth - 1, next_visited)
            for o in opp_ids
        ]
        return float(np.mean(scores))

    def opponent_difficulty_score(self, fighter_id, cutoff_fight_id, depth=3):
        """
        ODS: normalized (~1.0 baseline) score representing how tough a
        fighter's recent opposition has been, cascaded 3 degrees deep.
        """
        key = (fighter_id, cutoff_fight_id)
        if key in self.ods_cache:
            return self.ods_cache[key]

        strength = self._recursive_strength(fighter_id, cutoff_fight_id, depth, frozenset())
        ods = 1.0 + (strength - self.base_elo) / 400.0
        ods = float(np.clip(ods, 0.5, 1.8))
        self.ods_cache[key] = ods
        return ods

    def run(self):
        """Process all fights chronologically, updating Elo with ODS-scaled
        K-factor gains/losses."""
        for row in self.db.fights_df.itertuples(index=False):
            a, b = row.winner_id, row.loser_id
            fid = row.fight_id

            ra, rb = self.elo[a], self.elo[b]
            exp_a = self._expected(ra, rb)
            exp_b = 1.0 - exp_a

            ods_b = self.opponent_difficulty_score(b, fid)  # difficulty of the one A just beat
            ods_a = self.opponent_difficulty_score(a, fid)  # difficulty of the one B just lost to

            gain_a = self.k * (1 - exp_a) * ods_b
            loss_b = self.k * (0 - exp_b) * ods_a

            self.elo[a] = ra + gain_a
            self.elo[b] = rb + loss_b

        # snapshot final ODS (using full history) for downstream layers
        last_fid = int(self.db.fights_df["fight_id"].max()) + 1
        for fid in self.db.fighters_df["fighter_id"]:
            self._final_ods[fid] = self.opponent_difficulty_score(fid, last_fid)
        return self.elo

    def final_ods(self, fighter_id):
        return self._final_ods.get(fighter_id, 1.0)

    def win_probability(self, fighter_a_id, fighter_b_id):
        ra = self.elo.get(fighter_a_id, self.base_elo)
        rb = self.elo.get(fighter_b_id, self.base_elo)
        return self._expected(ra, rb)


# ---------------------------------------------------------------------------
# LAYER 2: Physical Matchup Logistic Regression
# ---------------------------------------------------------------------------
class PhysicalMatchupModel:
    """Logistic Regression trained strictly on physical trait discrepancies:
    height, reach, age, and stance matchup."""

    FEATURES = ["height_diff", "reach_diff", "age_diff", "stance_match"]

    def __init__(self, database):
        self.db = database
        self.model = LogisticRegression(max_iter=1000)
        self._fitted = False

    def _row_features(self, fid_a, fid_b):
        a = self.db.get_fighter(fid_a)
        b = self.db.get_fighter(fid_b)
        height_diff = a["height_in"] - b["height_in"]
        reach_diff = a["reach_in"] - b["reach_in"]
        age_diff = a["age"] - b["age"]
        stance_match = 1.0 if a["stance"] == b["stance"] else 0.0
        return [height_diff, reach_diff, age_diff, stance_match]

    def fit(self):
        X, y = [], []
        for row in self.db.fights_df.itertuples(index=False):
            X.append(self._row_features(row.winner_id, row.loser_id))
            y.append(1)
            X.append(self._row_features(row.loser_id, row.winner_id))
            y.append(0)
        X = np.array(X)
        y = np.array(y)
        self.model.fit(X, y)
        self._fitted = True
        return self

    def win_probability(self, fid_a, fid_b):
        if not self._fitted:
            self.fit()
        feats = np.array([self._row_features(fid_a, fid_b)])
        proba = self.model.predict_proba(feats)[0][1]
        return float(proba)


# ---------------------------------------------------------------------------
# LAYER 3: Contextual MMA Performance Stats
# ---------------------------------------------------------------------------
class ContextualStatsModel:
    """Aggregates each fighter's career striking/takedown metrics, then
    scales those raw stats by the fighter's historical ODS (from Layer 1) to
    produce a context-adjusted performance composite."""

    def __init__(self, database, elo_engine):
        self.db = database
        self.elo_engine = elo_engine
        self._career_stats = {}

    def _career_averages(self, fighter_id):
        if fighter_id in self._career_stats:
            return self._career_stats[fighter_id]

        strike_acc, td_def, volume = [], [], []
        for row in self.db.get_history(fighter_id):
            if row["winner_id"] == fighter_id:
                strike_acc.append(row["winner_strike_accuracy"])
                td_def.append(row["winner_td_defense"])
                volume.append(row["winner_strikes_landed"])
            else:
                strike_acc.append(row["loser_strike_accuracy"])
                td_def.append(row["loser_td_defense"])
                volume.append(row["loser_strikes_landed"])

        if not strike_acc:
            stats = {"strike_accuracy": 0.44, "td_defense": 0.62, "volume": 60.0}
        else:
            stats = {
                "strike_accuracy": float(np.mean(strike_acc)),
                "td_defense": float(np.mean(td_def)),
                "volume": float(np.mean(volume)),
            }
        self._career_stats[fighter_id] = stats
        return stats

    def contextual_composite(self, fighter_id):
        stats = self._career_averages(fighter_id)
        ods = self.elo_engine.final_ods(fighter_id)
        # normalize volume onto a 0-1-ish scale relative to a 150-strike ceiling
        norm_volume = min(stats["volume"] / 150.0, 1.0)
        raw_composite = (0.45 * stats["strike_accuracy"] +
                          0.35 * stats["td_defense"] +
                          0.20 * norm_volume)
        return raw_composite * ods

    def win_probability(self, fid_a, fid_b, decay_penalty_a=1.0, decay_penalty_b=1.0):
        comp_a = self.contextual_composite(fid_a) * decay_penalty_a
        comp_b = self.contextual_composite(fid_b) * decay_penalty_b
        # logistic squashing of the composite differential
        diff = comp_a - comp_b
        prob_a = 1.0 / (1.0 + math.exp(-6.0 * diff))
        return prob_a, comp_a, comp_b


# ---------------------------------------------------------------------------
# LAYER 5: Wear-and-Tear Decay System
# ---------------------------------------------------------------------------
class DecaySystem:
    """
    If a fighter's most recent bout ended in a Split Decision, their next
    fight's performance metrics take a penalty. The penalty scales with the
    ODS of the opponent from that split-decision bout, and decays
    exponentially across subsequent fights.
    """

    def __init__(self, database, elo_engine, base_penalty=0.18, decay_rate=0.55):
        self.db = database
        self.elo_engine = elo_engine
        self.base_penalty = base_penalty
        self.decay_rate = decay_rate

    def penalty_scalar(self, fighter_id):
        history = self.db.get_history(fighter_id)
        if not history:
            return 1.0

        # find most recent split decision and how many fights have occurred since
        split_idx = None
        for idx, row in enumerate(history):
            if row["method"] == "Split Decision":
                split_idx = idx

        if split_idx is None:
            return 1.0

        split_row = history[split_idx]
        opponent_id = (split_row["loser_id"] if split_row["winner_id"] == fighter_id
                        else split_row["winner_id"])
        ods_of_bout = self.elo_engine.final_ods(opponent_id)

        fights_since = (len(history) - 1) - split_idx  # 0 if it was the very last fight
        penalty = self.base_penalty * ods_of_bout * math.exp(-self.decay_rate * fights_since)
        scalar = 1.0 - penalty
        return float(np.clip(scalar, 0.5, 1.0))


# ---------------------------------------------------------------------------
# LAYER 4: Weighted Ensemble
# ---------------------------------------------------------------------------
class EnsembleModel:
    ELO_WEIGHT = 0.40
    CONTEXTUAL_WEIGHT = 0.35
    PHYSICAL_WEIGHT = 0.25

    def __init__(self, database):
        self.db = database
        self.elo_engine = RecursiveEloEngine(database)
        self.physical_model = PhysicalMatchupModel(database)
        self.contextual_model = ContextualStatsModel(database, self.elo_engine)
        self.decay_system = DecaySystem(database, self.elo_engine)
        self._ready = False

    def fit(self):
        self.elo_engine.run()
        self.physical_model.fit()
        self._ready = True
        return self

    def predict(self, fid_a, fid_b):
        if not self._ready:
            self.fit()

        elo_prob = self.elo_engine.win_probability(fid_a, fid_b)
        physical_prob = self.physical_model.win_probability(fid_a, fid_b)

        decay_a = self.decay_system.penalty_scalar(fid_a)
        decay_b = self.decay_system.penalty_scalar(fid_b)
        contextual_prob, comp_a, comp_b = self.contextual_model.win_probability(
            fid_a, fid_b, decay_a, decay_b
        )

        ensemble_prob = (
            self.ELO_WEIGHT * elo_prob +
            self.CONTEXTUAL_WEIGHT * contextual_prob +
            self.PHYSICAL_WEIGHT * physical_prob
        )
        ensemble_prob = float(np.clip(ensemble_prob, 0.01, 0.99))

        return {
            "elo_prob": elo_prob,
            "physical_prob": physical_prob,
            "contextual_prob": contextual_prob,
            "ensemble_prob": ensemble_prob,
            "elo_a": self.elo_engine.elo[fid_a],
            "elo_b": self.elo_engine.elo[fid_b],
            "ods_a": self.elo_engine.final_ods(fid_a),
            "ods_b": self.elo_engine.final_ods(fid_b),
            "decay_penalty_a": decay_a,
            "decay_penalty_b": decay_b,
            "contextual_composite_a": comp_a,
            "contextual_composite_b": comp_b,
        }


# ---------------------------------------------------------------------------
# LAYER 6: Monte Carlo Simulator
# ---------------------------------------------------------------------------
class MonteCarloSimulator:
    def __init__(self, n_iterations=10000, std=0.09, seed=None):
        self.n_iterations = n_iterations
        self.std = std
        self.rng = np.random.default_rng(seed)

    def simulate(self, ensemble_prob):
        samples = self.rng.normal(ensemble_prob, self.std, self.n_iterations)
        samples = np.clip(samples, 0.0, 1.0)

        outcomes = self.rng.random(self.n_iterations) < samples
        win_pct = float(outcomes.mean())

        ci_low, ci_high = np.percentile(samples, [2.5, 97.5])

        return {
            "win_pct": win_pct,
            "ci_low": float(ci_low),
            "ci_high": float(ci_high),
            "samples": samples,
        }


# ---------------------------------------------------------------------------
# Top-level Prediction Engine
# ---------------------------------------------------------------------------
class PredictionEngine:
    def __init__(self, database):
        self.db = database
        self.ensemble = EnsembleModel(database)
        self.ensemble.fit()

    def predict_fight(self, name_a, name_b, mc_iterations=10000):
        fighter_a = self.db.get_fighter_by_name(name_a)
        fighter_b = self.db.get_fighter_by_name(name_b)
        fid_a, fid_b = fighter_a["fighter_id"], fighter_b["fighter_id"]

        layer_results = self.ensemble.predict(fid_a, fid_b)

        mc = MonteCarloSimulator(n_iterations=mc_iterations)
        mc_result = mc.simulate(layer_results["ensemble_prob"])

        return {
            "fighter_a": fighter_a["name"],
            "fighter_b": fighter_b["name"],
            **layer_results,
            "monte_carlo": mc_result,
        }
