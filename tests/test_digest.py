import contextlib
import copy
import io
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

from maintainer_digest.cli import main, validate_snapshot
from maintainer_digest.github import GitHubClient, GitHubError, NoRedirect, iso, repository, timestamp
from maintainer_digest.report import analyze, markdown, safe_link, safe_text

ROOT = Path(__file__).resolve().parents[1]
SINCE = timestamp("2026-10-15T00:00:00Z")
UNTIL = timestamp("2026-10-22T00:00:00Z")


def fixture():
    return json.loads((ROOT / "examples/demo-snapshot.json").read_text(encoding="utf-8"))


class MetricsTests(unittest.TestCase):
    def report(self, **kwargs):
        return analyze(fixture()["repositories"][0], SINCE, UNTIL, **kwargs)

    def test_issue_endpoint_pr_entries_are_not_issues(self):
        self.assertEqual(self.report()["counts"]["new_issues"], 3)

    def test_merges_use_merged_timestamp_not_closed_state(self):
        report = self.report()
        self.assertEqual(report["counts"]["merged_pulls"], 1)
        self.assertEqual(report["sections"]["merged_pulls"][0]["number"], 21)

    def test_bot_filter(self):
        report = self.report(exclude_bots=True)
        self.assertEqual(report["counts"]["new_issues"], 2)
        self.assertNotIn("dependency-bot[bot]", report["authors"])

    def test_draft_pr_not_in_action_list_but_in_total(self):
        counts = self.report()["counts"]
        self.assertEqual(counts["all_open_pulls"], 2)
        self.assertEqual(counts["open_pulls"], 1)

    def test_stale_uses_updated_not_created(self):
        report = self.report()
        self.assertEqual([x["number"] for x in report["sections"]["stale_issues"]], [3])

    def test_stale_threshold_includes_exact_boundary(self):
        data = fixture()["repositories"][0]
        data["open_issues"][1]["updated_at"] = "2026-09-22T00:00:00Z"
        self.assertEqual(analyze(data, SINCE, UNTIL)["counts"]["stale_issues"], 1)

    def test_releases_use_publication_and_keep_prereleases(self):
        sections = self.report()["sections"]
        self.assertEqual({x["tag_name"] for x in sections["releases"]}, {"v1.2.0", "v1.3.0rc1"})

    def test_window_is_start_inclusive_end_exclusive(self):
        data = fixture()["repositories"][0]
        item = copy.deepcopy(data["issues"][0])
        item["created_at"] = "2026-10-22T00:00:00Z"
        data["issues"].append(item)
        self.assertEqual(analyze(data, SINCE, UNTIL)["counts"]["new_issues"], 3)

    def test_empty_repository(self):
        data = {"repository": "owner/repo", **{k: [] for k in ("issues", "pulls", "open_issues", "open_pulls", "releases")}}
        self.assertTrue(all(x == 0 for x in analyze(data, SINCE, UNTIL)["counts"].values()))

    def test_render_limit_does_not_change_counts(self):
        report = self.report()
        output = markdown([report], "2026-10-22T00:00:00Z", limit=1)
        self.assertIn("2 more items omitted", output)
        self.assertEqual(report["counts"]["new_issues"], 3)

    def test_markdown_handles_untrusted_titles(self):
        self.assertEqual(safe_text("<script>|[x]\n"), "&lt;script&gt;\\|\\[x\\] ")
        self.assertNotIn("javascript:", safe_link("x", "javascript:alert(1)"))
        self.assertNotIn("evil.test", safe_link("x", "https://github.com@evil.test/a"))
        self.assertIn("%29", safe_link("x", "https://github.com/a/b/releases/tag/a)"))

    def test_chinese_report(self):
        output = markdown([self.report()], "2026-10-22T00:00:00Z", lang="zh")
        self.assertIn("开源维护简报", output)
        self.assertIn("统计口径", output)


class ClientTests(unittest.TestCase):
    def test_repository_validation(self):
        self.assertEqual(repository("https://github.com/owner/repo.git/"), "owner/repo")
        for value in ("../repo", "owner/..", "https://evil.test/repo", "owner/repo?foo=1", "owner/repo/issues"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                repository(value)

    def test_timestamp_normalizes_timezone(self):
        self.assertEqual(timestamp("2026-10-22T08:00:00+08:00"), UNTIL)
        self.assertEqual(timestamp("2026-10-22"), UNTIL)

    def test_timestamp_replay_preserves_fractional_seconds(self):
        original = timestamp("2026-10-22T00:00:00.123456Z")
        self.assertEqual(timestamp(iso(original)), original)

    def test_paginate_and_deduplicate(self):
        client = GitHubClient()
        client.get = Mock(side_effect=[([{"id": 1}], '<x>; rel="next"'), ([{"id": 1}, {"id": 2}], "")])
        self.assertEqual([x["id"] for x in client.pages("/a", {}, "test")], [1, 2])
        self.assertEqual(client.get.call_args_list[1].args[1]["page"], 2)

    def test_page_cap_is_explicit(self):
        client = GitHubClient(max_pages=1)
        client.get = Mock(return_value=([{"id": 1}], '<x>; rel="next"'))
        client.pages("/a", {}, "test")
        self.assertIn("incomplete", client.warnings[0])

    def test_pull_cutoff_prevents_scanning_entire_history(self):
        client = GitHubClient(max_pages=1)
        client.get = Mock(return_value=([{"id": 1, "updated_at": "2020-01-01T00:00:00Z"}], '<x>; rel="next"'))
        client.pages("/a", {}, "test", stop_before=SINCE)
        self.assertEqual(client.warnings, [])

    def test_collection_has_five_distinct_read_endpoints(self):
        client = GitHubClient()
        client.pages = Mock(return_value=[])
        data = client.collect("owner/repo", SINCE)
        self.assertEqual(client.pages.call_count, 5)
        self.assertEqual(data["repository"], "owner/repo")
        self.assertIn("since", client.pages.call_args_list[0].args[1])
        self.assertEqual(client.pages.call_args_list[0].args[1]["since"], "2026-10-14T23:59:59Z")
        self.assertEqual(client.pages.call_args_list[2].args[1]["state"], "open")

    def test_http_request_and_auth_headers(self):
        response = Mock()
        response.read = Mock(return_value=b"[]")
        response.headers = {}
        context = Mock()
        context.__enter__ = Mock(return_value=response)
        context.__exit__ = Mock(return_value=False)
        opener = Mock()
        opener.open.return_value = context
        client = GitHubClient(token="test-token", opener=opener)
        self.assertEqual(client.get("/repos/a/b/issues", {"page": 2}), ([], ""))
        request = opener.open.call_args.args[0]
        self.assertEqual(request.get_header("Authorization"), "Bearer test-token")
        self.assertEqual(request.get_method(), "GET")
        self.assertTrue(request.full_url.startswith("https://api.github.com/"))

    def test_rate_limit_error_is_actionable_and_does_not_leak_token(self):
        opener = Mock()
        opener.open.side_effect = HTTPError("https://api.github.com", 403, "bad", {"X-RateLimit-Reset": "1792627200"}, None)
        with self.assertRaises(GitHubError) as raised:
            GitHubClient(token="secret", opener=opener).get("/x", {})
        self.assertIn("reset", str(raised.exception))
        self.assertNotIn("secret", str(raised.exception))

    def test_transient_errors_retry_with_bounded_backoff(self):
        opener = Mock()
        opener.open.side_effect = HTTPError("https://api.github.com", 503, "bad", {}, None)
        sleep = Mock()
        with self.assertRaises(GitHubError):
            GitHubClient(opener=opener, sleep=sleep).get("/x", {})
        self.assertEqual(opener.open.call_count, 3)
        self.assertEqual([x.args[0] for x in sleep.call_args_list], [1, 2])

    def test_network_failure_has_no_raw_exception(self):
        opener = Mock()
        opener.open.side_effect = URLError("sensitive raw detail")
        with self.assertRaisesRegex(GitHubError, "Network request failed"):
            GitHubClient(opener=opener, sleep=Mock()).get("/x", {})

    def test_redirect_does_not_forward_credentials(self):
        handler = NoRedirect()
        self.assertIsNone(handler.redirect_request(None, None, 302, "moved", {}, "https://evil.test"))


class CLITests(unittest.TestCase):
    def run_main(self, args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(args)
        return code, out.getvalue(), err.getvalue()

    def test_offline_replay_is_deterministic_and_makes_no_network_requests(self):
        args = ["--input", str(ROOT / "examples/demo-snapshot.json"), "--lang", "zh"]
        with patch("maintainer_digest.cli.GitHubClient") as client:
            first = self.run_main(args)
            second = self.run_main(args)
        self.assertEqual(first, second)
        self.assertEqual(first[0], 0)
        client.assert_not_called()

    def test_live_collection_and_replay_match(self):
        snapshot = fixture()
        with tempfile.TemporaryDirectory() as directory, patch("maintainer_digest.cli.GitHubClient") as client:
            client.return_value.collect.return_value = snapshot["repositories"][0]
            saved = Path(directory) / "snapshot.json"
            summary = Path(directory) / "summary.json"
            code, live, _ = self.run_main(["--repo", "example-org/example-project", "--since", "2026-10-15",
                                          "--until", "2026-10-22", "--save-data", str(saved), "--json-output", str(summary)])
            self.assertEqual(code, 0)
            self.assertEqual(self.run_main(["--input", str(saved)])[1], live)
            self.assertEqual(json.loads(summary.read_text())["reports"][0]["counts"]["merged_pulls"], 1)

    def test_invalid_snapshot_is_reported_without_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            bad = Path(directory) / "bad.json"
            bad.write_text('{"schema_version":99}')
            code, _, err = self.run_main(["--input", str(bad)])
            self.assertEqual(code, 1)
            self.assertIn("schema_version", err)
            self.assertNotIn("Traceback", err)

    def test_incomplete_data_strict_mode_writes_warning_and_returns_two(self):
        snapshot = fixture()
        snapshot["repositories"][0]["warnings"] = ["test: collection incomplete"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "partial.json"
            path.write_text(json.dumps(snapshot))
            code, out, err = self.run_main(["--input", str(path), "--strict"])
        self.assertEqual(code, 2)
        self.assertIn("Incomplete collection", out)
        self.assertIn("collection incomplete", err)

    def test_rejects_reversed_dates_before_network(self):
        code, _, err = self.run_main(["--repo", "a/b", "--since", "2026-10-23", "--until", "2026-10-22"])
        self.assertEqual(code, 1)
        self.assertIn("precede", err)

    def test_conflicting_output_paths_rejected(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            main(["--input", str(ROOT / "examples/demo-snapshot.json"), "--output", "same", "--json-output", "same"])
        self.assertEqual(raised.exception.code, 2)

    def test_offline_window_override_rejected(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(["--input", "snapshot.json", "--days", "7"])

    def test_secrets_are_redacted_from_error_messages(self):
        with patch.dict(os.environ, {"GH_TOKEN": "a-secret-value"}), patch("maintainer_digest.cli.GitHubClient") as client:
            client.return_value.collect.side_effect = GitHubError("bad a-secret-value")
            code, _, err = self.run_main(["--repo", "a/b"])
        self.assertEqual(code, 1)
        self.assertIn("[REDACTED]", err)
        self.assertNotIn("a-secret-value", err)


if __name__ == "__main__":
    unittest.main()
