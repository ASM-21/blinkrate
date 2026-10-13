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


# Stored results keep 9 significant figures, the precision that reproduces.
# Below it, the last digits of a result belong to the platform rather than the
# code: library versions, numpy's SIMD paths and the BLAS kernels picked for the
# CPU all reorder floating-point arithmetic. Measured on every stored value
# across five library stacks and three CPU code paths (Intel AVX-512 and AMD
# Zen 3 kernels, selected by environment variable on one machine), the largest
# disagreement is 5.4e-12 relative, on a regression p-value near 1e-13. At the
# 12 figures stored before v1.2.0 that p-value changed its last digit under Zen 3
# kernels, which fails CI's byte check. At 9, every value sits at least 70 times
# its cross-platform spread from a rounding boundary. Tests that compare a
# stored value with an exact one allow twice the largest rounding error (1e-8
# relative). The most precise figure the prose quotes has five significant
# figures (100.00%).
SIG_FIGS = 9


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
    # Every result is stamped filed_data / model_implied before it can be
    # written, and an undeclared key refuses to save. See provenance.py.
    from .provenance import stamp
    payload = stamp(name, payload)
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
