"""EIA-861 reliability ingestion, harmonized across filing-year layout changes.

One row per (utility, state, year). Every track reads through `load_panel()`.

Layout note that costs you the whole dataset if you miss it: the 2013-2015 CSVs
and the 2022 XLSX are the same form with different headers. The CSVs carry two
header rows and name the columns "SAIDI With MED"; 2022 carries three header
rows, names them "SAIDI (minutes per year)" under a merged banner, and adds
Ownership and CAIDI columns that the earlier years do not have. Both files put
the IEEE-standard block and the Other-standard block side by side with
IDENTICAL column names, so a naive header read silently keeps only one of them.
We index by position, not by name.

Missing values are the literal string "." in EIA files, and customer counts are
comma-formatted strings. Both become NaN under a default read.
"""

from __future__ import annotations

import functools
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"

# Column positions in the 2013-2015 CSV layout (0-indexed, after 2 header rows).
_LEGACY_COLS = {
    "year": 0, "utility_id": 1, "utility_name": 2, "state": 3,
    "ieee_saidi_with": 4, "ieee_saidi_without": 5, "ieee_saidi_no_los": 6,
    "ieee_saifi_with": 7, "ieee_saifi_without": 8, "ieee_saifi_no_los": 9,
    "ieee_customers": 10, "ieee_max_voltage": 11, "ieee_auto_outage": 12,
    "other_saidi_with": 13, "other_saidi_without": 14,
    "other_saifi_with": 15, "other_saifi_without": 16,
    "other_customers": 17, "other_inactive": 18, "other_momentary": 19,
    "other_max_voltage": 20, "other_auto_outage": 21,
}

# Column positions in the 2022 XLSX layout (0-indexed, after 3 header rows).
_MODERN_COLS = {
    "year": 0, "utility_id": 1, "utility_name": 2, "state": 3, "ownership": 4,
    "ieee_saidi_with": 5, "ieee_saifi_with": 6, "ieee_caidi_with": 7,
    "ieee_saidi_without": 8, "ieee_saifi_without": 9, "ieee_caidi_without": 10,
    "ieee_saidi_no_los": 11, "ieee_saifi_no_los": 12, "ieee_caidi_no_los": 13,
    "ieee_customers": 14, "ieee_max_voltage": 15, "ieee_auto_outage": 16,
    "other_saidi_with": 17, "other_saifi_with": 18, "other_caidi_with": 19,
    "other_saidi_without": 20, "other_saifi_without": 21, "other_caidi_without": 22,
    "other_customers": 23, "other_inactive": 24, "other_momentary": 25,
    "other_max_voltage": 26, "other_auto_outage": 27,
}

NUMERIC = [
    "ieee_saidi_with", "ieee_saidi_without", "ieee_saidi_no_los",
    "ieee_saifi_with", "ieee_saifi_without", "ieee_saifi_no_los",
    "ieee_caidi_with", "ieee_caidi_without", "ieee_caidi_no_los",
    "ieee_customers", "ieee_max_voltage",
    "other_saidi_with", "other_saidi_without",
    "other_saifi_with", "other_saifi_without",
    "other_caidi_with", "other_caidi_without",
    "other_customers", "other_max_voltage",
]


def _to_num(s: pd.Series) -> pd.Series:
    """EIA writes missing as '.', thousands with commas, and blanks as ' '."""
    return pd.to_numeric(
        s.astype(str).str.strip().str.replace(",", "", regex=False).replace(
            {".": np.nan, "": np.nan, "nan": np.nan, "None": np.nan}
        ),
        errors="coerce",
    )


def _reshape(raw: pd.DataFrame, colmap: dict) -> pd.DataFrame:
    out = pd.DataFrame(index=raw.index)
    for name, pos in colmap.items():
        out[name] = raw.iloc[:, pos] if pos < raw.shape[1] else np.nan
    for c in NUMERIC:
        out[c] = _to_num(out[c]) if c in out.columns else np.nan
    for c in ("utility_name", "state", "ownership"):
        if c in out.columns:
            out[c] = out[c].astype(str).str.strip()
        else:
            out[c] = pd.NA
    out["year"] = _to_num(out["year"]).astype("Int64")
    out["utility_id"] = _to_num(out["utility_id"]).astype("Int64")
    return out


def load_year(year: int) -> pd.DataFrame:
    """Load one filing year in the harmonized wide layout."""
    if year in (2013, 2014, 2015):
        raw = pd.read_csv(
            DATA_DIR / f"Reliability_{year}.csv", header=None, skiprows=2,
            dtype=str, keep_default_na=False,
        )
        df = _reshape(raw, _LEGACY_COLS)
    elif year == 2022:
        raw = pd.read_excel(
            DATA_DIR / "Reliability_2022.xlsx", sheet_name="Reliability_States",
            header=None, skiprows=3, dtype=str,
        )
        df = _reshape(raw, _MODERN_COLS)
    else:
        raise ValueError(f"no vendored EIA-861 reliability file for {year}")
    return df[df["utility_id"].notna()].reset_index(drop=True)


def _standardize(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse the side-by-side IEEE / Other blocks into one set of columns.

    A utility-state row reports under exactly one standard. `standard` records
    which, because that choice is itself discretionary and track 3 tests it.
    """
    is_ieee = df["ieee_saidi_with"].notna()
    is_other = df["other_saidi_with"].notna()

    out = df[["year", "utility_id", "utility_name", "state", "ownership"]].copy()
    out["standard"] = np.where(is_ieee, "IEEE", np.where(is_other, "Other", None))
    for metric in ("saidi_with", "saidi_without", "saifi_with", "saifi_without",
                   "caidi_with", "caidi_without", "customers"):
        out[metric] = np.where(is_ieee, df[f"ieee_{metric}"], df[f"other_{metric}"])
    # LOS variant is only collected under the IEEE block.
    out["saidi_no_los"] = df["ieee_saidi_no_los"]
    out["saifi_no_los"] = df["ieee_saifi_no_los"]
    out["reports_both"] = is_ieee & is_other
    return out[out["standard"].notna()].reset_index(drop=True)


OWNERSHIP_MAP = {
    "Investor Owned": "IOU", "Investor-Owned": "IOU",
    "Cooperative": "Coop", "Municipal": "Municipal",
    "Political Subdivision": "Municipal", "State": "Public",
    "Federal": "Public", "Retail Power Marketer": "Marketer",
    "Behind the Meter": "Other", "Community Choice Aggregator": "Other",
    "Municipal Mrkt Authority": "Municipal", "Wholesale Power Marketer": "Marketer",
}


def _ownership_lookup() -> pd.DataFrame:
    """utility_id -> ownership class, from the Sales file (2013-2015) or Frame (2022).

    The pre-2022 reliability files carry no ownership column; the Sales to
    Ultimate Customers file for the same year does, so ownership for the early
    panel is joined in rather than assumed constant.
    """
    frames = []
    for year in (2013, 2014, 2015):
        s = pd.read_csv(DATA_DIR / f"Sales_Ult_Cust_{year}.csv", header=None,
                        skiprows=3, dtype=str, keep_default_na=False,
                        usecols=[0, 1, 7], names=["year", "utility_id", "ownership"])
        frames.append(s)
    f = pd.read_excel(DATA_DIR / "Frame_2022.xlsx", sheet_name="Frame",
                      header=0, dtype=str, usecols=[0, 1, 5])
    f.columns = ["year", "utility_id", "ownership"]
    frames.append(f)
    look = pd.concat(frames, ignore_index=True)
    look["year"] = _to_num(look["year"]).astype("Int64")
    look["utility_id"] = _to_num(look["utility_id"]).astype("Int64")
    look["ownership"] = look["ownership"].astype(str).str.strip()
    look = look.dropna(subset=["utility_id", "year"])
    return look.drop_duplicates(subset=["year", "utility_id"], keep="first")


@functools.lru_cache(maxsize=1)
def load_panel(years: tuple[int, ...] = (2013, 2014, 2015, 2022)) -> pd.DataFrame:
    """The BlinkRate analysis panel: one row per utility-state-year.

    Adds the two derived quantities every track leans on:
      excluded_minutes = SAIDI(with MED) - SAIDI(without MED)
      retained_share   = SAIDI(without) / SAIDI(with)   [called `r` in the paper]
    """
    df = pd.concat([_standardize(load_year(y)) for y in years], ignore_index=True)

    look = _ownership_lookup()
    df = df.merge(look, on=["year", "utility_id"], how="left",
                  suffixes=("", "_joined"))
    df["ownership"] = df["ownership"].replace({"nan": np.nan, "None": np.nan, "": np.nan})
    df["ownership"] = df["ownership"].fillna(df["ownership_joined"])
    df = df.drop(columns=["ownership_joined"])
    df["ownership_class"] = df["ownership"].map(OWNERSHIP_MAP).fillna("Other")

    df["excluded_minutes"] = df["saidi_with"] - df["saidi_without"]
    with np.errstate(divide="ignore", invalid="ignore"):
        df["retained_share"] = np.where(
            df["saidi_with"] > 0, df["saidi_without"] / df["saidi_with"], np.nan
        )
        df["excluded_share"] = 1.0 - df["retained_share"]
        df["saifi_retained_share"] = np.where(
            df["saifi_with"] > 0, df["saifi_without"] / df["saifi_with"], np.nan
        )
    df["log_customers"] = np.log(df["customers"].where(df["customers"] > 0))
    return df


def analysis_sample(min_customers: int = 100) -> pd.DataFrame:
    """Panel filtered to rows where the with/without pair is usable.

    Drops rows with missing or non-positive SAIDI, a retained share outside
    [0, 1] (a reporting error: you cannot have more outage time after removing
    days than before), and very small utilities where a single event dominates.
    """
    df = load_panel().copy()
    ok = (
        df["saidi_with"].notna() & df["saidi_without"].notna()
        & (df["saidi_with"] > 0)
        & (df["retained_share"] >= 0) & (df["retained_share"] <= 1)
        & (df["customers"] >= min_customers)
    )
    df = df[ok].copy()
    df["utility_state"] = (
        df["utility_id"].astype(str) + "_" + df["state"].astype(str)
    )
    return df.reset_index(drop=True)


def rejected_rows(min_customers: int = 100) -> pd.DataFrame:
    """Everything analysis_sample() drops, with the reason, so exclusions are auditable."""
    df = load_panel().copy()
    reasons = []
    for _, r in df.iterrows():
        why = []
        if pd.isna(r["saidi_with"]) or pd.isna(r["saidi_without"]):
            why.append("missing_saidi")
        elif r["saidi_with"] <= 0:
            why.append("nonpositive_saidi_with")
        elif not (0 <= r["retained_share"] <= 1):
            why.append("retained_share_out_of_range")
        if pd.isna(r["customers"]) or r["customers"] < min_customers:
            why.append("too_small_or_missing_customers")
        reasons.append(";".join(why) if why else "")
    df["reject_reason"] = reasons
    return df[df["reject_reason"] != ""].reset_index(drop=True)
