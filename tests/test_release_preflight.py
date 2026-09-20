import contextlib
import io
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.release_preflight import REQUIRED_ACTION_PATHS, main, run_preflight


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def make_repo(root: Path, version: str = "1.4.0", with_actions: bool = True) -> Path:
    repo = root / "work"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "user.name", "t")
    (repo / "VERSION").write_text(version + "\n")
    if with_actions:
        for rel in REQUIRED_ACTION_PATHS:
            (repo / rel).parent.mkdir(parents=True, exist_ok=True)
            (repo / rel).write_text("name: x\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "init")
    return repo


class ReleasePreflightTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_passes_when_all_three_hold(self):
        repo = make_repo(self.root)
        self.assertEqual(run_preflight(repo, "v1.4.0", remote=None), [])

    def test_existing_local_tag_fails_with_tag_and_sha(self):
        repo = make_repo(self.root)
        git(repo, "tag", "v1.4.0")
        sha = git(repo, "rev-parse", "v1.4.0")
        failures = run_preflight(repo, "v1.4.0", remote=None)
        self.assertEqual(len(failures), 1)
        self.assertIn("tag-absent", failures[0])
        self.assertIn("'v1.4.0'", failures[0])
        self.assertIn(sha, failures[0])

    def test_existing_remote_tag_fails_with_remote_and_sha(self):
        repo = make_repo(self.root)
        bare = self.root / "origin.git"
        subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
        git(repo, "remote", "add", "origin", str(bare))
        git(repo, "tag", "v1.4.0")
        git(repo, "push", "-q", "origin", "v1.4.0")
        sha = git(repo, "rev-parse", "v1.4.0")
        git(repo, "tag", "-d", "v1.4.0")  # only the remote has it now
        failures = run_preflight(repo, "v1.4.0", remote="origin")
        self.assertEqual(len(failures), 1)
        self.assertIn("remote 'origin'", failures[0])
        self.assertIn(sha, failures[0])

    def test_unreachable_remote_fails_closed(self):
        repo = make_repo(self.root)
        git(repo, "remote", "add", "origin", str(self.root / "nope.git"))
        failures = run_preflight(repo, "v1.4.0", remote="origin")
        self.assertEqual(len(failures), 1)
        self.assertIn("could not query remote 'origin'", failures[0])

    def test_absent_remote_tag_passes(self):
        repo = make_repo(self.root)
        bare = self.root / "origin.git"
        subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
        git(repo, "remote", "add", "origin", str(bare))
        self.assertEqual(run_preflight(repo, "v1.4.0", remote="origin"), [])

    def test_tag_already_cut_skips_only_assertion_one(self):
        repo = make_repo(self.root)
        git(repo, "tag", "v1.4.0")
        self.assertEqual(run_preflight(repo, "v1.4.0", remote=None, tag_already_cut=True), [])

    def test_version_mismatch_names_both_values(self):
        repo = make_repo(self.root, version="1.3.0")
        failures = run_preflight(repo, "v1.4.0", remote=None)
        self.assertEqual(len(failures), 1)
        self.assertIn("version", failures[0])
        self.assertIn("'1.3.0'", failures[0])
        self.assertIn("'1.4.0'", failures[0])

    def test_version_read_from_ref_not_working_tree(self):
        repo = make_repo(self.root, version="1.4.0")
        (repo / "VERSION").write_text("9.9.9\n")  # uncommitted edit must not matter
        self.assertEqual(run_preflight(repo, "v1.4.0", remote=None), [])

    def test_tag_without_v_prefix_fails(self):
        repo = make_repo(self.root)
        failures = run_preflight(repo, "1.4.0", remote=None)
        self.assertEqual(len(failures), 1)
        self.assertIn("'1.4.0' does not start with 'v'", failures[0])

    def test_missing_version_file_fails(self):
        repo = make_repo(self.root)
        git(repo, "rm", "-q", "VERSION")
        git(repo, "commit", "-q", "-m", "drop VERSION")
        failures = run_preflight(repo, "v1.4.0", remote=None)
        self.assertEqual(len(failures), 1)
        self.assertIn("cannot read VERSION at ref 'HEAD'", failures[0])

    def test_missing_action_path_names_each_missing_path(self):
        repo = make_repo(self.root, with_actions=False)
        failures = run_preflight(repo, "v1.4.0", remote=None)
        self.assertEqual(len(failures), len(REQUIRED_ACTION_PATHS))
        for path in REQUIRED_ACTION_PATHS:
            self.assertTrue(any(repr(path) in f and "'HEAD'" in f for f in failures))

    def test_action_path_checked_at_ref_not_working_tree(self):
        repo = make_repo(self.root)
        first = git(repo, "rev-parse", "HEAD")
        git(repo, "rm", "-q", REQUIRED_ACTION_PATHS[0])
        git(repo, "commit", "-q", "-m", "drop action")
        self.assertEqual(run_preflight(repo, "v1.4.0", ref=first, remote=None), [])
        self.assertEqual(len(run_preflight(repo, "v1.4.0", remote=None)), 1)

    def test_cli_exit_codes_and_output(self):
        repo = make_repo(self.root)
        err, out = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main(["--repo", str(repo), "--tag", "v1.4.0", "--remote", ""]), 0)
        self.assertIn("preflight ok", out.getvalue())
        git(repo, "tag", "v1.4.0")
        with contextlib.redirect_stderr(err):
            self.assertEqual(main(["--repo", str(repo), "--tag", "v1.4.0", "--remote", ""]), 1)
        self.assertIn("preflight FAILED [1/3 tag-absent]", err.getvalue())
        self.assertEqual(
            main(["--repo", str(repo), "--tag", "v1.4.0", "--remote", "", "--tag-already-cut"]), 0
        )


if __name__ == "__main__":
    unittest.main()
