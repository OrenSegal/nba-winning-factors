"""Copy generated results next to the site pages for static hosting.

Run after `python -m nbawin.run`, then deploy the site/ directory.
metrics.json is rewritten with NaN -> null because browsers reject NaN in JSON.
"""

import json
import math
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def clean(x):
    if isinstance(x, float) and math.isnan(x):
        return None
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items()}
    if isinstance(x, list):
        return [clean(v) for v in x]
    return x


for name in ["report.md", "calibration.png", "coefficients.png", "walk_forward.png", "factor_atlas.csv", "dashboard.json"]:
    shutil.copy(ROOT / "results" / name, ROOT / "site" / name)
metrics = json.loads((ROOT / "results" / "metrics.json").read_text())
(ROOT / "site" / "metrics.json").write_text(json.dumps(clean(metrics), allow_nan=False))
