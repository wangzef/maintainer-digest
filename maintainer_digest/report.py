"""Deterministic metrics and Markdown presentation; no model-generated claims."""

import html
import re
from datetime import timedelta
from urllib.parse import urlsplit

from .github import iso, repository, timestamp


def is_bot(item):
    user = item.get("user") or item.get("author") or {}
    return user.get("type") == "Bot" or user.get("login", "").endswith("[bot]")


def analyze(data, since, until, stale_days=30, exclude_bots=False):
    def inside(item, field):
        return bool(item.get(field)) and since <= timestamp(item[field]) < until

    def eligible(items):
        return [x for x in items if not (exclude_bots and is_bot(x))]

    issues = eligible([x for x in data["issues"] if "pull_request" not in x])
    pulls = eligible(data["pulls"])
    # Backlog reflects the collection snapshot, never an inferred historical state.
    open_issues = eligible([x for x in data["open_issues"] if "pull_request" not in x and x.get("state") == "open"])
    open_pulls = eligible([x for x in data["open_pulls"] if x.get("state") == "open"])
    cutoff = until - timedelta(days=stale_days)
    sections = {
        "new_issues": [x for x in issues if inside(x, "created_at")],
        "closed_issues": [x for x in issues if inside(x, "closed_at")],
        "new_pulls": [x for x in pulls if inside(x, "created_at")],
        "merged_pulls": [x for x in pulls if inside(x, "merged_at")],
        "stale_issues": [x for x in open_issues if timestamp(x["updated_at"]) <= cutoff],
        "unassigned_issues": [x for x in open_issues if not x.get("assignees")],
        "open_pulls": [x for x in open_pulls if not x.get("draft")],
        "releases": eligible([x for x in data["releases"] if not x.get("draft") and inside(x, "published_at")]),
    }
    for key, field in (("new_issues", "created_at"), ("closed_issues", "closed_at"),
                       ("new_pulls", "created_at"), ("merged_pulls", "merged_at"), ("releases", "published_at")):
        sections[key].sort(key=lambda x: (x[field], x.get("number", 0)), reverse=True)
    for key in ("stale_issues", "unassigned_issues", "open_pulls"):
        sections[key].sort(key=lambda x: (x["updated_at"], x.get("number", 0)))
    # Authors, not all reviewers/commenters: the underlying endpoints cannot establish those.
    authors = sorted({(x.get("user") or {}).get("login", "")
                      for x in sections["new_issues"] + sections["new_pulls"]} - {""})
    return {"repository": repository(data["repository"]), "since": iso(since), "until": iso(until),
            "stale_days": stale_days, "exclude_bots": exclude_bots, "warnings": data.get("warnings", []),
            "counts": {**{k: len(v) for k, v in sections.items()}, "open_issues": len(open_issues),
                       "all_open_pulls": len(open_pulls), "authors": len(authors)},
            "authors": authors, "sections": sections}


TEXT = {
    "en": {
        "title": "Maintainer Digest", "window": "Activity window (UTC, end exclusive)", "collected": "Snapshot collected",
        "metric": "Metric", "count": "Count", "new_issues": "New issues", "closed_issues": "Issues closed",
        "new_pulls": "New pull requests", "merged_pulls": "Merged pull requests", "open_issues": "Open issues · snapshot",
        "all_open_pulls": "Open pull requests · snapshot", "authors": "New issue / PR authors",
        "stale_issues": "Quiet open issues · snapshot", "unassigned_issues": "Unassigned open issues · snapshot",
        "open_pulls": "Open non-draft PRs · snapshot", "releases": "Published releases",
        "none": "None in the collected data.", "more": "more items omitted from this list; totals include them.",
        "warnings": "Incomplete collection", "id": "Item", "item_title": "Title", "author": "Author",
        "updated": "Last updated (UTC)", "tag": "Tag", "published": "Published (UTC)", "pre": "prerelease",
        "notes": "How to read this report",
        "method": "Activity counts use timestamps in [start, end). Backlog lists use the current collection snapshot, not historical state. Closed issues count their latest closure; reopen/close cycles are not reconstructed. Quiet means no update for at least {days} days relative to the window end. Open PRs may already have reviews; this is not a review-status queue.",
        "authors_note": "Authors covers newly opened issues and PRs, not every contributor. Lists show at most {limit} items each. Bot authors {bots}. Counts may overlap (for example, a new issue closed in the same week).",
        "included": "included", "excluded": "excluded", "source": "Sources: GitHub REST API. No LLM or external analytics service.",
        "snapshot_note": "Snapshot collection is sequential; repository state may change while collecting.",
    },
    "zh": {
        "title": "开源维护简报", "window": "活动时间范围（UTC，含起点、不含终点）", "collected": "快照采集时间",
        "metric": "指标", "count": "数量", "new_issues": "新增 Issue", "closed_issues": "关闭 Issue",
        "new_pulls": "新增 PR", "merged_pulls": "合并 PR", "open_issues": "未关闭 Issue · 当前快照",
        "all_open_pulls": "未关闭 PR · 当前快照", "authors": "新增 Issue / PR 的作者数",
        "stale_issues": "长期未更新的 Issue · 当前快照", "unassigned_issues": "未指派的 Issue · 当前快照",
        "open_pulls": "非草稿开放 PR · 当前快照", "releases": "发布版本",
        "none": "已采集的数据中没有符合条件的条目。", "more": "个条目未在列表展示；统计总数包含这些条目。",
        "warnings": "采集不完整", "id": "条目", "item_title": "标题", "author": "作者",
        "updated": "最近更新（UTC）", "tag": "标签", "published": "发布时间（UTC）", "pre": "预发布",
        "notes": "统计口径",
        "method": "活动指标按 [起点, 终点) 内的时间戳统计。待办列表来自采集时的当前快照，不代表历史状态。关闭 Issue 按最近一次关闭时间统计，不重建反复开启/关闭事件。长期未更新指相对范围终点至少 {days} 天未更新。开放 PR 可能已经收到评审，此列表不代表尚未评审。",
        "authors_note": "作者数仅覆盖新增 Issue 和 PR，不代表全部贡献者。每个列表最多展示 {limit} 条。机器人作者：{bots}。指标可能重叠，例如同一周内新建又关闭的 Issue。",
        "included": "计入", "excluded": "排除", "source": "数据来源：GitHub REST API。无需大模型或第三方分析服务。",
        "snapshot_note": "快照通过顺序请求采集，期间仓库状态可能发生变化。",
    },
}


def safe_text(value):
    text = re.sub(r"[\x00-\x1f\x7f]", " ", str(value))
    text = html.escape(text, quote=False)
    for char in ("\\", "|", "[", "]", "*", "_", "`", "~", "!"):
        text = text.replace(char, "\\" + char)
    return text


def safe_link(label, url):
    parts = urlsplit(str(url))
    if parts.scheme != "https" or parts.netloc != "github.com":
        return safe_text(label)
    url = str(url).replace("(", "%28").replace(")", "%29").replace(" ", "%20")
    if any(ord(c) < 32 for c in url) or "<" in url or ">" in url:
        return safe_text(label)
    return "[" + safe_text(label) + "](" + url + ")"


def markdown(reports, collected_at, lang="en", limit=20, notice=None):
    t = TEXT[lang]
    lines = ["# " + t["title"], "", t["collected"] + ": " + safe_text(collected_at) + "", ""]
    if notice:
        lines += ["> " + safe_text(notice), ""]
    for report in reports:
        lines += ["## " + safe_link(report["repository"], "https://github.com/" + report["repository"]), "",
                  t["window"] + ": `" + report["since"] + "` → `" + report["until"] + "`", ""]
        if report["warnings"]:
            lines += ["### " + t["warnings"], ""] + ["- " + safe_text(w) for w in report["warnings"]] + [""]
        lines += [f"| {t['metric']} | {t['count']} |", "| --- | ---: |"]
        lines += [f"| {t[key]} | {value} |" for key, value in report["counts"].items()]
        lines.append("")
        for key, items in report["sections"].items():
            lines += ["### " + t[key], ""]
            if not items:
                lines += [t["none"], ""]
                continue
            release = key == "releases"
            labels = (t["tag"], t["item_title"], t["published"]) if release else (t["id"], t["item_title"], t["author"], t["updated"])
            lines += ["| " + " | ".join(labels) + " |", "| " + " | ".join("---" for _ in labels) + " |"]
            for item in items[:limit]:
                if release:
                    title = item.get("name") or item["tag_name"]
                    if item.get("prerelease"):
                        title += " (" + t["pre"] + ")"
                    cells = [safe_link(item["tag_name"], item.get("html_url", "")), safe_text(title), safe_text(item["published_at"])]
                else:
                    cells = [safe_link("#" + str(item["number"]), item.get("html_url", "")), safe_text(item["title"]),
                             safe_text((item.get("user") or {}).get("login", "—")), safe_text(item["updated_at"])]
                lines.append("| " + " | ".join(cells) + " |")
            if len(items) > limit:
                lines += ["", str(len(items) - limit) + " " + t["more"]]
            lines.append("")
        lines += ["### " + t["notes"], "", t["method"].format(days=report["stale_days"]), "",
                  t["authors_note"].format(limit=limit, bots=t["excluded"] if report["exclude_bots"] else t["included"]), ""]
    lines += [t["snapshot_note"], "", t["source"], ""]
    return "\n".join(lines)
