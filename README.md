# Maintainer Digest

**Turn GitHub maintenance activity into a readable, source-linked weekly report.**

[简体中文](README.zh-CN.md) · [Example report](examples/report.en.md) · [Contributing](CONTRIBUTING.md)

Maintaining a repository means moving between issues, pull requests, releases, and quiet backlog items. Maintainer Digest collects those signals into Markdown and JSON, with an explicit time window and links back to GitHub. Run it locally or in GitHub Actions.

**Python 3.10+ · zero runtime dependencies · no LLM or API subscription · MIT licensed**

## Try it in 30 seconds

```bash
git clone https://github.com/wangzef/maintainer-digest.git
cd maintainer-digest

# Offline demo, no account or network required. All demo data is synthetic.
python3 -m maintainer_digest --input examples/demo-snapshot.json --lang en

# Report on a public repository (replace OWNER/REPO).
python3 -m maintainer_digest --repo OWNER/REPO --days 7 --output report.md
```

Optional installation from this checkout:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
maintainer-digest --help
```

The package has **not** been published to PyPI. Install from source as above.

## What you get

| Signal | Purpose |
| --- | --- |
| New and closed issues | See incoming work and recent resolutions |
| New and merged PRs | Understand code delivery, using actual merge timestamps |
| Quiet and unassigned open issues | Find backlog items worth revisiting |
| Open non-draft PRs | See current work, oldest update first |
| Published releases, including prereleases | Keep track of releases by publication date |
| Counts and source links | Verify the report without trusting a generated narrative |
| Replayable snapshots | Reproduce and translate reports without another API request |

This is a portable report for maintainers and project handoffs. GitHub's web interface remains useful for interactive exploration; this tool focuses on reproducibility, bilingual output, explicit counting rules, and automation.

## Usage

```bash
# Aggregate multiple repositories; each gets its own section.
python3 -m maintainer_digest \
  --repo pallets/flask --repo psf/requests \
  --days 7 --lang zh --output reports/weekly.md

# A fixed UTC interval: inclusive start, exclusive end.
python3 -m maintainer_digest --repo OWNER/REPO \
  --since 2026-10-15 --until 2026-10-22 \
  --save-data snapshots/weekly.json --json-output reports/weekly.json \
  --output reports/weekly.md

# Translate/replay exactly the same collected data, offline.
python3 -m maintainer_digest --input snapshots/weekly.json \
  --lang zh --stale-days 30 --exclude-bots --output reports/weekly.zh.md

# Large repositories: increase the per-endpoint page limit.
# Strict mode writes a visibly incomplete report and returns exit code 2.
python3 -m maintainer_digest --repo OWNER/REPO --max-pages 50 --strict
```

Public repositories work without a token, subject to GitHub's unauthenticated rate limit. For regular use, set `GH_TOKEN` or `GITHUB_TOKEN` in your environment. `GH_TOKEN` takes precedence. The tool only makes GET requests to `https://api.github.com`; redirects are refused to avoid forwarding credentials. Do not put credentials in CLI arguments or committed files.

For a fine-grained token, choose only the repositories you need and grant **Issues: read** and **Pull requests: read**, plus **Contents: read** for release data in private repositories. Private-repository support depends on your token and organization policies. There is no Enterprise Server/custom API-host support in v0.1.

| Option | Default | Meaning |
| --- | --- | --- |
| `--repo` | required in live mode | `owner/name` or GitHub URL; repeatable |
| `--input` | none | Offline JSON snapshot, mutually exclusive with live repo/window flags |
| `--days` | 7 | Days before `--until`; mutually exclusive with `--since` |
| `--since`, `--until` | derived start, current UTC end | ISO 8601; dates/naive times mean UTC |
| `--lang` | `en` | `en` or `zh` |
| `--stale-days` | 30 | Quiet-issue threshold relative to window end |
| `--limit` | 20 | Display limit per list; does not reduce totals |
| `--max-pages` | 10 | 100 records/page, per endpoint; capped collections show warnings |
| `--exclude-bots` | off | Excludes records authored by GitHub `Bot` users or `[bot]` logins |
| `--output` | stdout | Markdown destination |
| `--json-output` | none | Metrics and report sections as JSON |
| `--save-data` | none | Raw API snapshot for replay |
| `--strict` | off | Exit 2 if a page limit caused incomplete collection |

Exit codes: `0` success, `1` collection/input/output error, `2` invalid CLI usage or incomplete collection with `--strict`.

## Use GitHub Actions

This repository includes two workflows:

- [CI](.github/workflows/ci.yml): tests on Python 3.10–3.14, package build/install smoke check.
- [Weekly digest](.github/workflows/digest.yml): manual or Monday schedule; reports on the current repository, adds a run summary, and uploads English/Chinese Markdown plus JSON metrics. No issue posting, commits, or repository writes.

After cloning this repository on GitHub, open **Actions → Weekly digest → Run workflow**. To use it in another project, copy this package's source and the workflow into that repository, or adapt the workflow to install a reviewed version of this tool. The included workflow expects the source in its checkout. Do not run untrusted source with secrets.

The workflow's `GITHUB_TOKEN` has read-only contents/issues/pull-request permissions. Large repositories may need a larger `--max-pages` value. Any incomplete result fails strict-mode workflow collection and retains the marked report as an artifact.

## Counting rules and limits

- Activity is based on `[since, until)` timestamps in UTC. `closed_at` is the **latest** issue closure; reopen/close cycles are not reconstructed. PR merges use `merged_at`, not `closed_at`.
- The issue endpoint also returns PRs; these are explicitly excluded from issue metrics.
- Open, unassigned, and quiet lists describe the **collection snapshot**, not historical backlog at `--until`. A historical date does not reconstruct past repository state. The snapshot is collected sequentially and is not an atomic transaction.
- Open PRs may already have reviews. This tool does not claim to detect PRs awaiting first review or calculate response times.
- The author count covers newly opened issues and PRs, not reviewers, commenters, or all contributors. Bot filtering checks authors, not every actor in an item's history.
- Activity categories overlap; do not add them together as a total contribution count.
- The client paginates issues, PRs, and releases; default cap is 1,000 records per endpoint. It scans PRs by descending update time, stopping after reaching the window's lower boundary. Releases are scanned without assuming publication order. Reports explicitly flag a cap rather than silently claiming complete totals.
- There is no review/comment timeline, event archive, deleted-item recovery, contributor ranking, AI narrative, or proof of program eligibility.
- GitHub is the only network destination. Saved snapshots and JSON reports can contain private repository metadata and author identities; review them before sharing. Issue/PR bodies are never rendered in Markdown, but raw API snapshots can contain them.

API references: [Issues](https://docs.github.com/en/rest/issues/issues), [Pull requests](https://docs.github.com/en/rest/pulls/pulls), [Releases](https://docs.github.com/en/rest/releases/releases), [Pagination](https://docs.github.com/en/rest/using-the-rest-api/using-pagination-in-the-rest-api).

## Development

```bash
python3 -m unittest discover -s tests -v
python3 -m maintainer_digest --input examples/demo-snapshot.json --lang en --output examples/report.en.md
python3 -m maintainer_digest --input examples/demo-snapshot.json --lang zh --output examples/report.zh-CN.md
```

See [CONTRIBUTING.md](CONTRIBUTING.md), [ROADMAP.md](ROADMAP.md), [SECURITY.md](SECURITY.md), and [CHANGELOG.md](CHANGELOG.md). Reports in `examples/` are labeled synthetic fixtures, not adoption or maintenance claims.

## License

[MIT](LICENSE). Maintained by [wangzef](https://github.com/wangzef). Contributions and reports of real maintainer needs are welcome.
