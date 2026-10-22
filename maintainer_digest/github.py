"""Read-only GitHub REST client. Never follows redirects with a token."""

import json
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener


class GitHubError(Exception):
    """A safe, human-readable collection error."""


def repository(value):
    value = value.strip()
    if value.startswith("https://github.com/"):
        value = value[len("https://github.com/"):].rstrip("/")
    if value.endswith(".git"):
        value = value[:-4]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_.-]+", value):
        raise ValueError("Repository must be owner/name or an https://github.com/owner/name URL")
    if value.split("/")[1] in (".", ".."):
        raise ValueError("Invalid repository name")
    return value


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("Expected an ISO 8601 timestamp")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def iso(value):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class GitHubClient:
    def __init__(self, token=None, max_pages=10, opener=None, sleep=time.sleep):
        self.token = token
        self.max_pages = max_pages
        self.opener = opener or build_opener(NoRedirect())
        self.sleep = sleep
        self.warnings = []
        self.requests = 0

    def get(self, path, params):
        url = "https://api.github.com" + path + "?" + urlencode(params)
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "maintainer-digest/0.1.0",
                   "X-GitHub-Api-Version": "2026-03-10"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        for attempt in range(3):
            self.requests += 1
            try:
                with self.opener.open(Request(url, headers=headers), timeout=30) as response:
                    data = json.load(response)
                    if not isinstance(data, list) or not all(isinstance(x, dict) for x in data):
                        raise GitHubError("Unexpected GitHub response; expected a list of objects")
                    return data, response.headers.get("Link", "")
            except HTTPError as exc:
                if exc.code in (500, 502, 503, 504) and attempt < 2:
                    self.sleep(2 ** attempt)
                    continue
                if exc.code in (301, 302, 307, 308):
                    message = "Repository redirected; use its current owner/name (redirects are not followed)"
                elif exc.code == 401:
                    message = "Authentication failed; check GH_TOKEN or GITHUB_TOKEN"
                elif exc.code == 404:
                    message = "Repository or endpoint not found; check spelling and token read permissions"
                elif exc.code in (403, 429):
                    reset = exc.headers.get("X-RateLimit-Reset", "")
                    retry = exc.headers.get("Retry-After", "")
                    message = "GitHub denied the request (permissions or rate limit)"
                    if reset.isdigit():
                        message += "; rate-limit reset: " + iso(datetime.fromtimestamp(int(reset), timezone.utc))
                    if retry.isdigit():
                        message += "; retry after " + retry + " seconds"
                else:
                    message = "GitHub returned HTTP " + str(exc.code)
                raise GitHubError(message) from None
            except (URLError, TimeoutError, OSError):
                if attempt < 2:
                    self.sleep(2 ** attempt)
                    continue
                raise GitHubError("Network request failed after 3 attempts; check connectivity") from None
            except (ValueError, UnicodeError):
                raise GitHubError("GitHub returned invalid JSON") from None

    def pages(self, path, params, label, stop_before=None):
        items, seen = [], set()
        for page in range(1, self.max_pages + 1):
            batch, link = self.get(path, {**params, "per_page": 100, "page": page})
            for item in batch:
                key = item.get("id", item.get("number"))
                if key is None or key not in seen:
                    items.append(item)
                    if key is not None:
                        seen.add(key)
            # This cutoff is used only with pull requests explicitly sorted by updated DESC.
            if stop_before and batch and all(
                timestamp(item["updated_at"]) < stop_before for item in batch
            ):
                break
            if not re.search(r'rel="next"', link):
                break
            if page == self.max_pages:
                self.warnings.append(f"{label}: stopped at {self.max_pages} pages; results are incomplete. Increase --max-pages.")
        return items

    def collect(self, repo, since):
        repo = repository(repo)
        path = "/repos/" + repo
        start = len(self.warnings)
        issues = self.pages(path + "/issues", {"state": "all", "sort": "updated", "direction": "desc",
                            "since": iso(since - timedelta(seconds=1))}, repo + " updated issues")
        pulls = self.pages(path + "/pulls", {"state": "all", "sort": "updated", "direction": "desc"},
                           repo + " updated pull requests", stop_before=since)
        open_issues = self.pages(path + "/issues", {"state": "open", "sort": "updated", "direction": "desc"},
                                 repo + " open issues")
        open_pulls = self.pages(path + "/pulls", {"state": "open", "sort": "updated", "direction": "desc"},
                                repo + " open pull requests")
        # Releases are ordered by created_at, not published_at. Scan all permitted pages.
        releases = self.pages(path + "/releases", {}, repo + " releases")
        return {"repository": repo, "issues": issues, "pulls": pulls, "open_issues": open_issues,
                "open_pulls": open_pulls, "releases": releases, "warnings": self.warnings[start:]}
