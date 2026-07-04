"""
scorecard.py
Digital scorecard for crowd-sourced UFC data collection. Teams submit a single
completed bout (both fighters + the per-fight striking / takedown / method
stats). Submissions are appended to separate CSVs under real_data/ so they are
clearly attributable and reviewable BEFORE being merged into the base dataset.

No license gate — data contributors don't need a paid account.

Run:
    streamlit run scorecard.py --server.port 8504

The core append/validation logic below is pure Python (no Streamlit) so it can
be unit-tested directly.
"""

import os

import pandas as pd

# ---------------------------------------------------------------------------
# Schema (mirrors utils.generate_all / real_data_loader OUTPUT format, which is
# what database.py consumes).
# ---------------------------------------------------------------------------
REAL_DATA_DIR = os.environ.get("REAL_DATA_DIR", "real_data")
SUBMITTED_FIGHTERS_CSV = os.path.join(REAL_DATA_DIR, "submitted_fighters.csv")
SUBMITTED_FIGHTS_CSV = os.path.join(REAL_DATA_DIR, "submitted_fights.csv")

FIGHTER_COLUMNS = [
    "fighter_id", "name", "weight_class", "stance",
    "height_in", "reach_in", "age", "elo",
]
FIGHT_COLUMNS = [
    "fight_id", "date", "weight_class", "winner_id", "loser_id", "method", "round",
    "winner_strikes_attempted", "winner_strikes_landed", "winner_strike_accuracy",
    "loser_strikes_attempted", "loser_strikes_landed", "loser_strike_accuracy",
    "winner_td_attempted", "winner_td_landed", "winner_td_defense",
    "loser_td_attempted", "loser_td_landed", "loser_td_defense",
]

WEIGHT_CLASSES = [
    "Flyweight", "Bantamweight", "Featherweight", "Lightweight",
    "Welterweight", "Middleweight", "Light Heavyweight", "Heavyweight",
]
STANCES = ["Orthodox", "Southpaw", "Switch"]
METHODS = ["KO/TKO", "Submission", "Unanimous Decision", "Split Decision", "Majority Decision"]

# Submitted fighters get IDs in a high range so they never collide with base
# scraped/mock IDs (1..~2,700).
SUBMITTED_ID_BASE = 900_000
BASE_ELO = 1500.0


# ---------------------------------------------------------------------------
# Pure helpers (unit-testable)
# ---------------------------------------------------------------------------
def load_df(path, columns):
    if os.path.exists(path):
        try:
            df = pd.read_csv(path)
            if not df.empty:
                return df
        except Exception:  # noqa: BLE001
            pass
    return pd.DataFrame(columns=columns)


def next_submitted_fighter_id(fighters_df):
    ids = [int(i) for i in fighters_df.get("fighter_id", pd.Series(dtype=int)).tolist()]
    submitted_ids = [i for i in ids if i >= SUBMITTED_ID_BASE]
    if submitted_ids:
        return max(submitted_ids) + 1
    return SUBMITTED_ID_BASE


def validate_fighter(f, corner_label=""):
    errors = []
    prefix = f"{corner_label} " if corner_label else ""
    if not str(f.get("name", "")).strip():
        errors.append(f"{prefix}fighter name is required.")
    if f.get("weight_class") not in WEIGHT_CLASSES:
        errors.append(f"{prefix}weight class is invalid.")
    if f.get("stance") not in STANCES:
        errors.append(f"{prefix}stance is invalid.")
    for field, lo, hi in [("height_in", 48, 90), ("reach_in", 48, 100), ("age", 18, 60)]:
        try:
            val = float(f.get(field))
        except (TypeError, ValueError):
            errors.append(f"{prefix}{field} must be a number.")
            continue
        if not (lo <= val <= hi):
            errors.append(f"{prefix}{field} out of range ({lo}-{hi}): {val}.")
    return errors


def validate_fight(fight):
    errors = []
    if fight.get("method") not in METHODS:
        errors.append("Method of victory is invalid.")
    try:
        rnd = int(fight.get("round"))
        if not (1 <= rnd <= 5):
            errors.append(f"Round must be 1-5, got {rnd}.")
    except (TypeError, ValueError):
        errors.append("Round must be an integer.")

    for who in ("winner", "loser"):
        att = fight.get(f"{who}_strikes_attempted")
        land = fight.get(f"{who}_strikes_landed")
        try:
            att_i, land_i = int(att), int(land)
            if att_i < 0 or land_i < 0:
                errors.append(f"{who} strike counts cannot be negative.")
            elif land_i > att_i:
                errors.append(f"{who} strikes landed ({land_i}) exceed attempted ({att_i}).")
        except (TypeError, ValueError):
            errors.append(f"{who} strike counts must be integers.")

        tda = fight.get(f"{who}_td_attempted")
        tdl = fight.get(f"{who}_td_landed")
        try:
            tda_i, tdl_i = int(tda), int(tdl)
            if tda_i < 0 or tdl_i < 0:
                errors.append(f"{who} takedown counts cannot be negative.")
            elif tdl_i > tda_i:
                errors.append(f"{who} takedowns landed ({tdl_i}) exceed attempted ({tda_i}).")
        except (TypeError, ValueError):
            errors.append(f"{who} takedown counts must be integers.")
    return errors


def _accuracy(landed, attempted):
    attempted = int(attempted)
    return round(int(landed) / attempted, 3) if attempted > 0 else 0.0


def _td_defense(landed_against, attempted_against):
    """Defense = fraction of opponent takedown attempts stopped."""
    attempted_against = int(attempted_against)
    if attempted_against <= 0:
        return 1.0
    return round(1 - int(landed_against) / attempted_against, 3)


def resolve_fighter_id(name, weight_class, stance, height_in, reach_in, age,
                       fighters_df, force_new=False):
    """Return (fighter_id, new_fighter_row_or_None, reused_existing_bool).

    If a submitted fighter with the same (case-insensitive) name already exists
    and force_new is False, its ID is reused instead of creating a duplicate."""
    name_norm = str(name).strip().lower()
    if not force_new and not fighters_df.empty:
        match = fighters_df[fighters_df["name"].astype(str).str.strip().str.lower() == name_norm]
        if not match.empty:
            return int(match.iloc[0]["fighter_id"]), None, True

    new_id = next_submitted_fighter_id(fighters_df)
    row = {
        "fighter_id": new_id,
        "name": str(name).strip(),
        "weight_class": weight_class,
        "stance": stance,
        "height_in": round(float(height_in), 1),
        "reach_in": round(float(reach_in), 1),
        "age": int(age),
        "elo": BASE_ELO,
    }
    return new_id, row, False


def name_exists(name, fighters_df):
    if fighters_df.empty:
        return False
    name_norm = str(name).strip().lower()
    return bool(
        (fighters_df["name"].astype(str).str.strip().str.lower() == name_norm).any()
    )


def append_submission(corner_a, corner_b, fight, winner_corner,
                      force_new_a=False, force_new_b=False):
    """Validate + persist one bout. Returns a result dict. Raises ValueError on
    validation failure. This is the testable entry point the UI calls."""
    errors = (
        validate_fighter(corner_a, "Corner A")
        + validate_fighter(corner_b, "Corner B")
        + validate_fight(fight)
    )
    if str(corner_a.get("name", "")).strip().lower() == str(corner_b.get("name", "")).strip().lower():
        errors.append("Corner A and Corner B cannot be the same fighter.")
    if winner_corner not in ("A", "B"):
        errors.append("Winner corner must be 'A' or 'B'.")
    if errors:
        raise ValueError("; ".join(errors))

    os.makedirs(REAL_DATA_DIR, exist_ok=True)
    fighters_df = load_df(SUBMITTED_FIGHTERS_CSV, FIGHTER_COLUMNS)
    fights_df = load_df(SUBMITTED_FIGHTS_CSV, FIGHT_COLUMNS)

    id_a, row_a, reused_a = resolve_fighter_id(
        corner_a["name"], corner_a["weight_class"], corner_a["stance"],
        corner_a["height_in"], corner_a["reach_in"], corner_a["age"],
        fighters_df, force_new=force_new_a,
    )
    new_rows = []
    if row_a is not None:
        new_rows.append(row_a)
        fighters_df = pd.concat([fighters_df, pd.DataFrame([row_a])], ignore_index=True)

    id_b, row_b, reused_b = resolve_fighter_id(
        corner_b["name"], corner_b["weight_class"], corner_b["stance"],
        corner_b["height_in"], corner_b["reach_in"], corner_b["age"],
        fighters_df, force_new=force_new_b,
    )
    if row_b is not None:
        new_rows.append(row_b)
        fighters_df = pd.concat([fighters_df, pd.DataFrame([row_b])], ignore_index=True)

    winner_id, loser_id = (id_a, id_b) if winner_corner == "A" else (id_b, id_a)

    # Order strike/td stats by winner vs loser.
    if winner_corner == "A":
        w, l = "a", "b"
    else:
        w, l = "b", "a"
    stats = fight  # already keyed winner_/loser_ by the caller

    next_fight_id = (int(fights_df["fight_id"].max()) + 1) if not fights_df.empty else 1
    fight_row = {
        "fight_id": next_fight_id,
        "date": fight.get("date"),
        "weight_class": fight.get("weight_class"),
        "winner_id": winner_id,
        "loser_id": loser_id,
        "method": fight.get("method"),
        "round": int(fight.get("round")),
        "winner_strikes_attempted": int(stats["winner_strikes_attempted"]),
        "winner_strikes_landed": int(stats["winner_strikes_landed"]),
        "winner_strike_accuracy": _accuracy(stats["winner_strikes_landed"], stats["winner_strikes_attempted"]),
        "loser_strikes_attempted": int(stats["loser_strikes_attempted"]),
        "loser_strikes_landed": int(stats["loser_strikes_landed"]),
        "loser_strike_accuracy": _accuracy(stats["loser_strikes_landed"], stats["loser_strikes_attempted"]),
        "winner_td_attempted": int(stats["winner_td_attempted"]),
        "winner_td_landed": int(stats["winner_td_landed"]),
        "winner_td_defense": _td_defense(stats["loser_td_landed"], stats["loser_td_attempted"]),
        "loser_td_attempted": int(stats["loser_td_attempted"]),
        "loser_td_landed": int(stats["loser_td_landed"]),
        "loser_td_defense": _td_defense(stats["winner_td_landed"], stats["winner_td_attempted"]),
    }
    fights_df = pd.concat([fights_df, pd.DataFrame([fight_row])], ignore_index=True)

    fighters_df[FIGHTER_COLUMNS].to_csv(SUBMITTED_FIGHTERS_CSV, index=False)
    fights_df[FIGHT_COLUMNS].to_csv(SUBMITTED_FIGHTS_CSV, index=False)

    return {
        "fight_id": next_fight_id,
        "winner_id": winner_id,
        "loser_id": loser_id,
        "new_fighters": [r["name"] for r in new_rows],
        "reused_a": reused_a,
        "reused_b": reused_b,
    }


# ---------------------------------------------------------------------------
# Streamlit UI
# ---------------------------------------------------------------------------
def _run_streamlit():
    import streamlit as st

    st.set_page_config(page_title="UFC Data Scorecard", page_icon="📝", layout="wide")
    st.title("📝 UFC Digital Scorecard")
    st.caption(
        "Submit a completed bout. Entries are saved to real_data/submitted_*.csv "
        "for review before being merged into the model dataset."
    )

    existing_fighters = load_df(SUBMITTED_FIGHTERS_CSV, FIGHTER_COLUMNS)

    def fighter_inputs(corner):
        st.markdown(f"### Corner {corner}")
        name = st.text_input(f"Name ({corner})", key=f"name_{corner}")
        wc = st.selectbox(f"Weight class ({corner})", WEIGHT_CLASSES, key=f"wc_{corner}")
        stance = st.selectbox(f"Stance ({corner})", STANCES, key=f"stance_{corner}")
        height = st.number_input(f"Height (in) ({corner})", 48.0, 90.0, 70.0, 0.5, key=f"h_{corner}")
        reach = st.number_input(f"Reach (in) ({corner})", 48.0, 100.0, 72.0, 0.5, key=f"r_{corner}")
        age = st.number_input(f"Age ({corner})", 18, 60, 30, 1, key=f"age_{corner}")
        dup = name.strip() and name_exists(name, existing_fighters)
        force_new = False
        if dup:
            st.warning(f"A submitted fighter named '{name}' already exists.")
            force_new = st.checkbox(
                f"Create a NEW fighter anyway (don't reuse existing '{name}')",
                key=f"forcenew_{corner}",
            )
        return {
            "name": name, "weight_class": wc, "stance": stance,
            "height_in": height, "reach_in": reach, "age": age,
        }, force_new

    col_a, col_b = st.columns(2)
    with col_a:
        corner_a, force_new_a = fighter_inputs("A")
    with col_b:
        corner_b, force_new_b = fighter_inputs("B")

    st.divider()
    st.markdown("### Fight result")
    fc1, fc2, fc3, fc4 = st.columns(4)
    date = fc1.date_input("Date")
    fight_wc = fc2.selectbox("Bout weight class", WEIGHT_CLASSES)
    method = fc3.selectbox("Method", METHODS)
    rnd = fc4.number_input("Final round", 1, 5, 3, 1)
    winner_corner = st.radio("Winner", ["A", "B"], horizontal=True)

    st.markdown("#### Per-fighter stats")
    sc1, sc2 = st.columns(2)
    stats_by_corner = {}
    for label, col in (("A", sc1), ("B", sc2)):
        with col:
            st.markdown(f"**Corner {label}**")
            sa = st.number_input(f"Strikes attempted ({label})", 0, 1000, 80, key=f"sa_{label}")
            sl = st.number_input(f"Strikes landed ({label})", 0, 1000, 35, key=f"sl_{label}")
            tda = st.number_input(f"Takedowns attempted ({label})", 0, 50, 2, key=f"tda_{label}")
            tdl = st.number_input(f"Takedowns landed ({label})", 0, 50, 1, key=f"tdl_{label}")
            stats_by_corner[label] = {
                "strikes_attempted": sa, "strikes_landed": sl,
                "td_attempted": tda, "td_landed": tdl,
            }

    if st.button("Submit bout", type="primary"):
        w_label, l_label = (winner_corner, "B" if winner_corner == "A" else "A")
        fight = {
            "date": str(date),
            "weight_class": fight_wc,
            "method": method,
            "round": int(rnd),
            "winner_strikes_attempted": stats_by_corner[w_label]["strikes_attempted"],
            "winner_strikes_landed": stats_by_corner[w_label]["strikes_landed"],
            "loser_strikes_attempted": stats_by_corner[l_label]["strikes_attempted"],
            "loser_strikes_landed": stats_by_corner[l_label]["strikes_landed"],
            "winner_td_attempted": stats_by_corner[w_label]["td_attempted"],
            "winner_td_landed": stats_by_corner[w_label]["td_landed"],
            "loser_td_attempted": stats_by_corner[l_label]["td_attempted"],
            "loser_td_landed": stats_by_corner[l_label]["td_landed"],
        }
        try:
            result = append_submission(
                corner_a, corner_b, fight, winner_corner,
                force_new_a=force_new_a, force_new_b=force_new_b,
            )
            st.success(
                f"Saved fight #{result['fight_id']}. "
                + (f"New fighters: {', '.join(result['new_fighters'])}. " if result["new_fighters"] else "")
                + "Thank you for contributing!"
            )
            st.info(
                f"Appended to `{SUBMITTED_FIGHTERS_CSV}` and `{SUBMITTED_FIGHTS_CSV}`."
            )
        except ValueError as e:
            st.error(f"Could not save — please fix: {e}")


if __name__ == "__main__":
    _run_streamlit()
