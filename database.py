"""
database.py
Lightweight in-memory data access layer over the generated fighters/fights
tables. Provides fight-history lookups used by the recursive ODS calculation
and by the decay system.
"""

import os

import pandas as pd
from utils import generate_all

SUBMITTED_FIGHTERS_CSV = os.path.join("real_data", "submitted_fighters.csv")
SUBMITTED_FIGHTS_CSV = os.path.join("real_data", "submitted_fights.csv")


class FightDatabase:
    def __init__(self, n_fighters=500, n_fights=2000, seed=42, include_submitted=True):
        self.fighters_df, self.fights_df = generate_all(n_fighters, n_fights, seed)
        if include_submitted:
            self._merge_submitted()
        self.fighters_df = self.fighters_df.set_index("fighter_id", drop=False)
        self._build_history_index()

    def _merge_submitted(self):
        """Additively merge crowd-sourced submissions (scorecard.py output) into
        the base dataset if the files are present. Purely additive and logged."""
        added_fighters = added_fights = 0

        if os.path.exists(SUBMITTED_FIGHTERS_CSV):
            try:
                sub_fighters = pd.read_csv(SUBMITTED_FIGHTERS_CSV)
            except Exception:  # noqa: BLE001
                sub_fighters = pd.DataFrame()
            if not sub_fighters.empty:
                sub_fighters = sub_fighters.reindex(columns=self.fighters_df.columns)
                existing_ids = set(self.fighters_df["fighter_id"])
                sub_fighters = sub_fighters[~sub_fighters["fighter_id"].isin(existing_ids)]
                if not sub_fighters.empty:
                    self.fighters_df = pd.concat(
                        [self.fighters_df, sub_fighters], ignore_index=True
                    )
                    added_fighters = len(sub_fighters)

        if os.path.exists(SUBMITTED_FIGHTS_CSV):
            try:
                sub_fights = pd.read_csv(SUBMITTED_FIGHTS_CSV)
            except Exception:  # noqa: BLE001
                sub_fights = pd.DataFrame()
            if not sub_fights.empty:
                sub_fights = sub_fights.reindex(columns=self.fights_df.columns)
                # Re-key fight_ids so they never collide with base fights.
                start = int(self.fights_df["fight_id"].max()) + 1 if not self.fights_df.empty else 1
                sub_fights = sub_fights.reset_index(drop=True)
                sub_fights["fight_id"] = range(start, start + len(sub_fights))
                self.fights_df = pd.concat(
                    [self.fights_df, sub_fights], ignore_index=True
                )
                # Normalize date (base is datetime, submitted is string) so the
                # chronological sort used by the recursive ODS/decay layers works.
                self.fights_df["date"] = pd.to_datetime(
                    self.fights_df["date"], errors="coerce"
                )
                self.fights_df = self.fights_df.sort_values("date").reset_index(drop=True)
                added_fights = len(sub_fights)

        if added_fighters or added_fights:
            print(
                f"[database] Merged submitted data: +{added_fighters} fighters, "
                f"+{added_fights} fights (from real_data/submitted_*.csv)."
            )

    def _build_history_index(self):
        """Maps fighter_id -> list of fight rows (chronological) they were in."""
        history = {fid: [] for fid in self.fighters_df["fighter_id"]}
        for _, row in self.fights_df.iterrows():
            history[row["winner_id"]].append(row)
            history[row["loser_id"]].append(row)
        # already chronological since fights_df is sorted by date
        self.fighter_history = history

    def get_fighter(self, fighter_id):
        return self.fighters_df.loc[fighter_id]

    def get_fighter_by_name(self, name):
        match = self.fighters_df[self.fighters_df["name"] == name]
        if match.empty:
            raise KeyError(f"No fighter named {name}")
        return match.iloc[0]

    def all_fighter_names(self):
        return sorted(self.fighters_df["name"].tolist())

    def get_history(self, fighter_id):
        """Chronological list of fight rows a fighter participated in."""
        return self.fighter_history.get(fighter_id, [])

    def get_opponents(self, fighter_id, limit=None):
        """Chronological list of opponent_ids a fighter has faced."""
        opps = []
        for f in self.get_history(fighter_id):
            opp = f["loser_id"] if f["winner_id"] == fighter_id else f["winner_id"]
            opps.append(opp)
        if limit:
            return opps[-limit:]
        return opps

    def last_fight(self, fighter_id):
        hist = self.get_history(fighter_id)
        return hist[-1] if hist else None

    def all_fights_chronological(self):
        return self.fights_df.itertuples(index=False)
