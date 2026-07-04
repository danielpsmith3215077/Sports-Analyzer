"""
utils.py
Mock historical UFC data generator.
Produces:
  - fighters_df: 500 fighters with physical traits
  - fights_df: 2000 time-ordered fights with methods, striking, and takedown metrics
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

RNG_SEED = 42

FIRST_NAMES = [
    "Alex","Jon","Mike","Chris","Dan","Kevin","Ryan","Josh","Matt","Nate",
    "Tony","Robbie","Justin","Cody","Max","Sean","Cain","Fabricio","Jose",
    "Conor","Israel","Kamaru","Charles","Dustin","Dricus","Bruno","Ilia",
    "Islam","Alexander","Merab","Belal","Leon","Colby","Gilbert","Tom",
    "Paulo","Anthony","Renato","Curtis","Jared","Derrick","Francis","Ciryl",
]

LAST_NAMES = [
    "Silva","Jones","Miller","Diaz","Costa","Lee","Bader","Emmett","Brown",
    "Diamond","Ferguson","Garbrandt","Gaethje","Poirier","Duplessis","Strickland",
    "Topuria","Makhachev","Volkanovski","Dvalishvili","Muhammad","Edwards",
    "Covington","Burns","Aspinall","Gane","Lewis","Blaydes","Pavlovich",
    "Adesanya","Whittaker","Cannonier","Hermansson","Vettori","Rockhold",
]

STANCES = ["Orthodox", "Southpaw", "Switch"]
METHODS = ["KO/TKO", "Submission", "Unanimous Decision", "Split Decision", "Majority Decision"]
METHOD_WEIGHTS = [0.32, 0.18, 0.30, 0.14, 0.06]

WEIGHT_CLASSES = [
    "Flyweight", "Bantamweight", "Featherweight", "Lightweight",
    "Welterweight", "Middleweight", "Light Heavyweight", "Heavyweight",
]


def _rng(seed=RNG_SEED):
    return np.random.default_rng(seed)


def generate_fighters(n=500, seed=RNG_SEED):
    rng = _rng(seed)
    ids = np.arange(1, n + 1)

    first = rng.choice(FIRST_NAMES, size=n)
    last = rng.choice(LAST_NAMES, size=n)
    names = []
    seen = {}
    for f, l in zip(first, last):
        base = f"{f} {l}"
        seen[base] = seen.get(base, 0) + 1
        names.append(base if seen[base] == 1 else f"{base} {seen[base]}")

    weight_class = rng.choice(WEIGHT_CLASSES, size=n)
    stance = rng.choice(STANCES, size=n, p=[0.65, 0.28, 0.07])

    wc_index = np.array([WEIGHT_CLASSES.index(w) for w in weight_class])
    base_height = 66 + wc_index * 1.6
    height = rng.normal(base_height, 2.2)
    height = np.clip(height, 61, 84)

    reach = height + rng.normal(1.5, 2.0, size=n)
    reach = np.clip(reach, height - 3, height + 8)

    age = rng.integers(21, 40, size=n)

    fighters = pd.DataFrame({
        "fighter_id": ids,
        "name": names,
        "weight_class": weight_class,
        "stance": stance,
        "height_in": np.round(height, 1),
        "reach_in": np.round(reach, 1),
        "age": age,
        "elo": 1500.0,
    })
    return fighters


def generate_fights(fighters_df, n_fights=2000, seed=RNG_SEED):
    """
    Generates time-ordered fights. Matchups are drawn preferentially within
    the same weight class. Each row is one completed fight with striking and
    takedown metrics for both corners plus the recorded method of victory.
    """
    rng = _rng(seed + 1)
    fighter_ids = fighters_df["fighter_id"].values
    wc_map = fighters_df.set_index("fighter_id")["weight_class"].to_dict()

    by_class = {}
    for fid, wc in wc_map.items():
        by_class.setdefault(wc, []).append(fid)

    start_date = datetime(2015, 1, 1)
    dates = sorted(start_date + timedelta(days=int(d)) for d in
                    rng.integers(0, 365 * 10, size=n_fights))

    rows = []
    for i in range(n_fights):
        wc = rng.choice(WEIGHT_CLASSES)
        pool = by_class.get(wc, list(fighter_ids))
        if len(pool) < 2:
            pool = list(fighter_ids)
        a, b = rng.choice(pool, size=2, replace=False)

        winner = a if rng.random() < 0.5 else b
        loser = b if winner == a else a

        method = rng.choice(METHODS, p=METHOD_WEIGHTS)
        rounds_ended = rng.integers(1, 6) if method != "KO/TKO" else rng.integers(1, 4)

        def strike_stats():
            attempted = rng.integers(30, 220)
            accuracy = np.clip(rng.normal(0.44, 0.10), 0.15, 0.85)
            landed = int(attempted * accuracy)
            return attempted, landed, round(float(accuracy), 3)

        w_att, w_land, w_acc = strike_stats()
        l_att, l_land, l_acc = strike_stats()

        def td_stats():
            attempted = rng.integers(0, 8)
            defense = np.clip(rng.normal(0.62, 0.15), 0.1, 0.95)
            landed = rng.binomial(attempted, 1 - defense) if attempted > 0 else 0
            return attempted, landed, round(float(defense), 3)

        w_td_att, w_td_land, w_td_def = td_stats()
        l_td_att, l_td_land, l_td_def = td_stats()

        rows.append({
            "fight_id": i + 1,
            "date": dates[i],
            "weight_class": wc,
            "winner_id": int(winner),
            "loser_id": int(loser),
            "method": method,
            "round": int(rounds_ended),
            "winner_strikes_attempted": int(w_att),
            "winner_strikes_landed": int(w_land),
            "winner_strike_accuracy": w_acc,
            "loser_strikes_attempted": int(l_att),
            "loser_strikes_landed": int(l_land),
            "loser_strike_accuracy": l_acc,
            "winner_td_attempted": int(w_td_att),
            "winner_td_landed": int(w_td_land),
            "winner_td_defense": w_td_def,
            "loser_td_attempted": int(l_td_att),
            "loser_td_landed": int(l_td_land),
            "loser_td_defense": l_td_def,
        })

    fights_df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    fights_df["fight_id"] = np.arange(1, len(fights_df) + 1)
    return fights_df


def generate_all(n_fighters=500, n_fights=2000, seed=RNG_SEED):
    fighters_df = generate_fighters(n_fighters, seed)
    fights_df = generate_fights(fighters_df, n_fights, seed)
    return fighters_df, fights_df


if __name__ == "__main__":
    f_df, fi_df = generate_all()
    print(f_df.shape, fi_df.shape)
    print(f_df.head())
    print(fi_df.head())
