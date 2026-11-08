"""Copy the generated report and figures next to site/index.html for static hosting.

Run after `python -m nbawin.run`, then deploy the site/ directory.
"""

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for name in ["report.md", "calibration.png", "coefficients.png", "walk_forward.png"]:
    shutil.copy(ROOT / "results" / name, ROOT / "site" / name)
