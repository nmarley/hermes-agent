"""A fresh process can configure file logging before importing the composition shim."""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path


def test_setup_logging_bootstraps_platform_hooks(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    root = Path(__file__).resolve().parents[2]
    script = textwrap.dedent(
        """
        import logging
        import sys
        from pathlib import Path

        import hermes_platform.logging as logging_setup

        home = Path(sys.argv[1])
        logging_setup.setup_logging(hermes_home=home)
        logging.getLogger("bootstrap.probe").warning("bootstrap-witness")
        logging_setup.flush_log_queue()
        errors = (home / "logs" / "errors.log").read_text(encoding="utf-8")
        assert "bootstrap-witness" in errors, errors
        """
    )
    env = os.environ.copy()
    env["HERMES_HOME"] = str(home)
    env["PYTHONPATH"] = "."
    subprocess.run(
        [sys.executable, "-c", script, str(home)],
        cwd=root,
        env=env,
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
