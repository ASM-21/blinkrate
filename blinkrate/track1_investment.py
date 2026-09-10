"""Track 1 - does capital deployment predict reliability?

SUBSTITUTION, STATED AT THE TOP. The track as scoped wanted FERC Form 1
capex-per-customer lagged one year against next-year SAIDI. ferc.gov is blocked
at the egress proxy and no mirrored Form 1 dataset exists on GitHub: the three
Form 1 repositories that turn up (catalyst-cooperative/ferc1-data-release,
catalyst-cooperative/rmi-ferc1-eia, doig007/Form1Analysis) ship extraction code
and schema documentation, not data. Search record in docs/DATA_ACCESS.md.

So the spending variable is gone and the question changes rather than getting
proxied quietly. What EIA-861 does publish for 2022 is physical capital
DEPLOYMENT: how many meters a utility has converted to AMI, and how many of its
distribution circuits carry voltage optimization. Those are outputs of capital
programs, observable per utility, and they are what this track regresses on.
The cost side is genuinely missing, so nothing here speaks to cost-effectiveness
- only to whether utilities that have deployed more have better numbers.

The second half of the track is a variance decomposition on the 2013-2015 panel,
which is worth as much as the regression. It puts a ceiling on how much any
utility-level investment variable could ever explain, by measuring how much of
the variance in SAIDI is a persistent utility effect versus a year-to-year
shock. A cross-sectional regressor can only ever reach the persistent part.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm

from .shared import ingest
from .shared.io import PALETTE, save_figure, save_results, style_axes

DATA_DIR = ingest.DATA_DIR


def load_deployment_2022() -> pd.DataFrame:
    """AMI share and voltage-optimized circuit share, per utility-state, 2022."""
    am = pd.read_excel(DATA_DIR / "Advanced_Meters_2022.xlsx", sheet_name="states",
                       header=None, skiprows=2, dtype=str)
    ami = pd.DataFrame({
        "utility_id": ingest._to_num(am.iloc[:, 1]).astype("Int64"),
        "state": am.iloc[:, 5].astype(str).str.strip(),
        "amr_total": ingest._to_num(am.iloc[:, 11]),
        "ami_total": ingest._to_num(am.iloc[:, 16]),
    })
    ami = ami.groupby(["utility_id", "state"], as_index=False).sum(min_count=1)

    ds = pd.read_excel(DATA_DIR / "Distribution_Systems_2022.xlsx",
                       sheet_name="Distribution_Systems_States",
                       header=None, skiprows=1, dtype=str)
    circ = pd.DataFrame({
        "utility_id": ingest._to_num(ds.iloc[:, 1]).astype("Int64"),
        "state": ds.iloc[:, 3].astype(str).str.strip(),
        "circuits": ingest._to_num(ds.iloc[:, 4]),
        "circuits_volt_opt": ingest._to_num(ds.iloc[:, 5]),
    })
    circ = circ.groupby(["utility_id", "state"], as_index=False).sum(min_count=1)
    return ami.merge(circ, on=["utility_id", "state"], how="outer")


def build_cross_section() -> pd.DataFrame:
    df = ingest.analysis_sample()
    df = df[df["year"] == 2022].copy()
    dep = load_deployment_2022()
    df = df.merge(dep, on=["utility_id", "state"], how="left")

    df["ami_share"] = (df["ami_total"] / df["customers"]).clip(0, 1)
    df["advanced_meter_share"] = (
        (df["ami_total"].fillna(0) + df["amr_total"].fillna(0)) / df["customers"]
    ).clip(0, 1)
    df["volt_opt_share"] = (df["circuits_volt_opt"] / df["circuits"]).clip(0, 1)
    df["customers_per_circuit"] = df["customers"] / df["circuits"].replace(0, np.nan)
    df["log_saidi_without"] = np.log(df["saidi_without"].where(df["saidi_without"] > 0))
    df["log_saidi_with"] = np.log(df["saidi_with"].where(df["saidi_with"] > 0))
    return df


def _ols(df: pd.DataFrame, y: str, regs: list[str], state_fe: bool,
         own_fe: bool) -> dict:
    cols = [y] + regs
    d = df.dropna(subset=cols).copy()
    X = d[regs].astype(float)
    if own_fe:
        X = pd.concat([X, pd.get_dummies(d["ownership_class"], prefix="own",
                                         drop_first=True, dtype=float)], axis=1)
    if state_fe:
        keep = d["state"].value_counts()
        keep = keep[keep >= 5].index
        st = d["state"].where(d["state"].isin(keep), "OTHER")
        X = pd.concat([X, pd.get_dummies(st, prefix="st", drop_first=True,
                                         dtype=float)], axis=1)
    X = sm.add_constant(X, has_constant="add")
    m = sm.OLS(d[y].astype(float), X).fit(
        cov_type="cluster", cov_kwds={"groups": d["state"]})
    return {
        "n": int(m.nobs), "r2": float(m.rsquared),
        "coefficients": {
            r: {"beta": float(m.params[r]), "se": float(m.bse[r]),
                "t": float(m.tvalues[r]), "p": float(m.pvalues[r]),
                "ci95": [float(m.conf_int().loc[r, 0]), float(m.conf_int().loc[r, 1])]}
            for r in regs
        },
        "state_fe": state_fe, "ownership_fe": own_fe,
        "se": "clustered by state",
    }


def cross_section_models(df: pd.DataFrame) -> dict:
    regs = ["ami_share", "volt_opt_share", "log_customers"]
    return {
        "log_saidi_without_raw": _ols(df, "log_saidi_without", regs, False, False),
        "log_saidi_without_fe": _ols(df, "log_saidi_without", regs, True, True),
        "log_saidi_with_fe": _ols(df, "log_saidi_with", regs, True, True),
        "retained_share_fe": _ols(df, "retained_share", regs, True, True),
    }


def variance_decomposition(years=(2013, 2014, 2015)) -> dict:
    """How much of SAIDI variance is a persistent utility effect?

    Balanced panel only: a utility must appear in every year, otherwise entry
    and exit masquerade as within-utility variation.
    """
    df = ingest.analysis_sample()
    df = df[df["year"].isin(years)].copy()
    df["log_saidi"] = np.log(df["saidi_without"].where(df["saidi_without"] > 0))
    df = df.dropna(subset=["log_saidi"])
    counts = df.groupby("utility_state")["year"].nunique()
    balanced = counts[counts == len(years)].index
    b = df[df["utility_state"].isin(balanced)]

    grand = b["log_saidi"].mean()
    means = b.groupby("utility_state")["log_saidi"].transform("mean")
    between = ((means - grand) ** 2).sum()
    within = ((b["log_saidi"] - means) ** 2).sum()
    total = between + within

    out = {
        "years": list(years),
        "n_utility_states_balanced": int(len(balanced)),
        "n_rows": int(len(b)),
        "share_between_utility": float(between / total),
        "share_within_utility": float(within / total),
        "sd_log_saidi": float(b["log_saidi"].std()),
    }
    # same decomposition on the with-MED series, for track 2's comparison
    b2 = b.assign(log_saidi_with=np.log(b["saidi_with"]))
    m2 = b2.groupby("utility_state")["log_saidi_with"].transform("mean")
    bet2 = ((m2 - b2["log_saidi_with"].mean()) ** 2).sum()
    wit2 = ((b2["log_saidi_with"] - m2) ** 2).sum()
    out["share_between_utility_with_med"] = float(bet2 / (bet2 + wit2))
    return out


def _fig(df: pd.DataFrame) -> None:
    import matplotlib.pyplot as plt
    d = df.dropna(subset=["ami_share", "log_saidi_without"])
    fig, ax = plt.subplots(figsize=(7.0, 4.3))
    ax.scatter(d["ami_share"], d["saidi_without"], s=14, alpha=0.45,
               color=PALETTE["with_med"], edgecolor="none")
    bins = np.linspace(0, 1, 11)
    d = d.assign(b=pd.cut(d["ami_share"], bins, include_lowest=True))
    g = d.groupby("b", observed=True)["saidi_without"].median()
    ax.plot([i.mid for i in g.index], g.values, color=PALETTE["without_med"],
            lw=2.2, marker="o", ms=4, label="binned median")
    ax.set_yscale("log")
    ax.set_xlabel("AMI share of customers, 2022")
    ax.set_ylabel("SAIDI without major event days (min/yr, log scale)")
    ax.set_title("Advanced metering deployment vs reported reliability, 2022",
                 loc="left", fontsize=11)
    ax.legend(frameon=False, fontsize=9)
    style_axes(ax)
    save_figure(fig, "track1_ami_vs_saidi")


def run(save: bool = True) -> dict:
    df = build_cross_section()
    out = {
        "substitution": (
            "FERC Form 1 capex unreachable; regressors are physical capital "
            "deployment (AMI share, voltage-optimized circuit share) from "
            "EIA-861 2022, not spending"
        ),
        "n_2022_matched": int(df["ami_share"].notna().sum()),
        "coverage": {
            "ami_share_median": float(df["ami_share"].median()),
            "volt_opt_share_median": float(df["volt_opt_share"].median()),
            "n_with_circuits": int(df["circuits"].notna().sum()),
        },
        "models": cross_section_models(df),
        "variance_decomposition": variance_decomposition(),
    }
    if save:
        _fig(df)
        save_results("track1_investment", out)
    return out


if __name__ == "__main__":  # pragma: no cover
    import json
    print(json.dumps(run(), indent=2, default=str))
