import subprocess
import tempfile
import sys
import os
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable

class GlobalArchitectureTests(unittest.TestCase):
    def run_cmd(self, *args: str, cwd: Path | None = None, env: dict[str, str] | None = None):
        return subprocess.run(
            [PYTHON, *args],
            cwd=cwd or ROOT,
            capture_output=True,
            text=True,
            env=env or os.environ,
        )

    def test_global_installation_and_multi_repo_usage(self) -> None:
        """The defining integration test for the new global architecture."""
        with tempfile.TemporaryDirectory() as home_dir, \
             tempfile.TemporaryDirectory() as repo_a_dir, \
             tempfile.TemporaryDirectory() as repo_b_dir:
            
            home = Path(home_dir)
            repo_a = Path(repo_a_dir)
            repo_b = Path(repo_b_dir)
            
            env = os.environ.copy()
            env["HOME"] = str(home)
            env["PYTHONPATH"] = str(ROOT)
            
            # Install PowerKit ONCE globally
            install_result = self.run_cmd(
                "-m", "powerkit", "init", "--platforms", "codex", "--yes",
                cwd=home,
                env=env
            )
            self.assertEqual(install_result.returncode, 0, f"STDOUT: {install_result.stdout}\nSTDERR: {install_result.stderr}")
            
            # Verify global assets exist
            self.assertTrue((home / ".powerkit" / "releases").is_dir())
            self.assertTrue((home / ".agents" / "skills").is_dir())
            
            # Now simulate Repo A using pk
            # We assume use of pk means checking that the repo does NOT get populated with core assets
            # In a real environment, the codex agent would execute the pk thin adapter in ~/.agents/skills/pk
            # We can run `powerkit init` in Repo A to see if it mutates the repo
            repo_a_init = self.run_cmd(
                "-m", "powerkit", "init", "--platforms", "codex", "--yes",
                cwd=repo_a,
                env=env
            )
            self.assertEqual(repo_a_init.returncode, 0, f"STDOUT: {repo_a_init.stdout}\nSTDERR: {repo_a_init.stderr}")
            
            # Repo A should contain ZERO core assets
            self.assertFalse((repo_a / ".agents").exists())
            self.assertFalse((repo_a / ".claude").exists())
            
            # Repeat for Repo B
            repo_b_init = self.run_cmd(
                "-m", "powerkit", "init", "--platforms", "codex", "--yes",
                cwd=repo_b,
                env=env
            )
            self.assertEqual(repo_b_init.returncode, 0, f"STDOUT: {repo_b_init.stdout}\nSTDERR: {repo_b_init.stderr}")
            
            # Repo B should contain ZERO core assets
            self.assertFalse((repo_b / ".agents").exists())
            self.assertFalse((repo_b / ".claude").exists())

if __name__ == "__main__":
    unittest.main()
