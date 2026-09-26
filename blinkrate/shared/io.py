"""Result and figure plumbing shared by every track."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"

PALETTE = {
    "with_med": "#1f3a5f", "without_med": "#c1443c", "accent": "#e08a3c",
    "muted": "#8a8f98", "grid": "#dcdfe4",
}


# Stored results keep 12 significant figures. The 15th-16th digits of some
# scipy p-values differ between scipy 1.15 and 1.17 (last-bit differences in
# the t-distribution CDF), which is noise, but it made the committed JSON
# differ byte-for-byte across library versions. Rounding here makes results
# byte-reproducible across the supported stack, which is what lets CI enforce
# that committed results equal regenerated ones. No claim anywhere in the prose
# uses more than four significant figures.
SIG_FIGS = 12


def _round_floats(obj):
    import math
    import numpy as np
    if isinstance(obj, dict):
        return {k: _round_floats(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_round_floats(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return _round_floats(obj.tolist())
    if isinstance(obj, (float, np.floating)):
        x = float(obj)
        if not math.isfinite(x) or x == 0.0:
            return x if math.isfinite(x) else None
        return float(f"{x:.{SIG_FIGS}g}")
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    return obj


def save_results(name: str, payload: dict) -> Path:
    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / f"{name}.json"
    path.write_text(json.dumps(_round_floats(payload), indent=2, sort_keys=True,
                               default=_default) + "\n")
    return path


def load_results(name: str) -> dict:
    return json.loads((RESULTS / f"{name}.json").read_text())


def _default(o):
    import numpy as np
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if np.isnan(o) else float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, np.bool_):
        return bool(o)
    raise TypeError(f"not JSON serializable: {type(o)}")


def style_axes(ax) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(True, color=PALETTE["grid"], linewidth=0.6, alpha=0.9)
    ax.set_axisbelow(True)


def save_figure(fig, name: str) -> Path:
    FIGURES.mkdir(parents=True, exist_ok=True)
    path = FIGURES / f"{name}.png"
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path
