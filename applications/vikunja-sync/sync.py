# /// script
# requires-python = ">=3.12"
# dependencies = ["requests"]
# ///
"""Move Vikunja tasks across kanban buckets to match the GitHub PRs that reference them.

A PR references a task by writing `vikunja#<id>` in its title or body. For each
referenced task, across all of its PRs:

- any PR open                      -> bucket "In review"
- all closed, at least one merged  -> bucket "Done"
- all closed, none merged          -> bucket "Backlog"

Each PR's link is commented on the task once. The script keeps no state: it
reads the task's current bucket and comments before changing anything.

Environment:
    GITHUB_TOKEN    read access to pull requests on every repo in REPOS
    VIKUNJA_URL     API base, e.g. http://vikunja.lan/api/v2
    VIKUNJA_TOKEN   Vikunja API token (tasks, comments, projects read)
    REPOS           comma-separated owner/name list
    LOOKBACK_DAYS   how far back to read closed PRs (default 7)
"""

import argparse
import logging
import os
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import requests

logger = logging.getLogger("vikunja-sync")

TASK_REF = re.compile(r"\bvikunja#(\d+)\b", re.IGNORECASE)
BUCKET_REVIEW = "In review"
BUCKET_DONE = "Done"
BUCKET_BACKLOG = "Backlog"
TIMEOUT = 30


@dataclass(frozen=True)
class PullRequest:
    repo: str
    number: int
    title: str
    url: str
    state: str  # "open", "merged" or "closed"
    task_ids: frozenset[int]


def parse_task_ids(*texts: str | None) -> frozenset[int]:
    return frozenset(int(m) for text in texts if text for m in TASK_REF.findall(text))


def choose_bucket(states: list[str]) -> str:
    if "open" in states:
        return BUCKET_REVIEW
    if "merged" in states:
        return BUCKET_DONE
    return BUCKET_BACKLOG


def group_by_task(pulls: list[PullRequest]) -> dict[int, list[PullRequest]]:
    by_task: dict[int, list[PullRequest]] = {}
    for pull in pulls:
        for task_id in pull.task_ids:
            by_task.setdefault(task_id, []).append(pull)
    return by_task


def fetch_pulls(session: requests.Session, repo: str, since: datetime) -> list[PullRequest]:
    """Return every open PR plus closed PRs updated since `since`, deduplicated."""
    seen: dict[int, PullRequest] = {}
    for state in ("open", "closed"):
        url = f"https://api.github.com/repos/{repo}/pulls"
        params = {"state": state, "sort": "updated", "direction": "desc", "per_page": 100}
        while url:
            response = session.get(url, params=params, timeout=TIMEOUT)
            response.raise_for_status()
            page = response.json()
            for raw in page:
                updated = datetime.fromisoformat(raw["updated_at"])
                if state == "closed" and updated < since:
                    url = None
                    break
                pr_state = "open" if raw["state"] == "open" else "merged" if raw["merged_at"] else "closed"
                seen[raw["number"]] = PullRequest(
                    repo=repo,
                    number=raw["number"],
                    title=raw["title"],
                    url=raw["html_url"],
                    state=pr_state,
                    task_ids=parse_task_ids(raw["title"], raw["body"]),
                )
            else:
                url = response.links.get("next", {}).get("url")
                params = None
    return list(seen.values())


class VikunjaClient:
    def __init__(self, base_url: str, token: str):
        self._base = base_url.rstrip("/")
        self._session = requests.Session()
        self._session.headers["Authorization"] = f"Bearer {token}"
        self._kanban: dict[int, tuple[int, dict[str, int], dict[int, int]]] = {}

    def _request(self, method: str, path: str, **kwargs) -> dict | list | None:
        response = self._session.request(method, f"{self._base}{path}", timeout=TIMEOUT, **kwargs)
        response.raise_for_status()
        return response.json() if response.text else None

    @staticmethod
    def _items(payload) -> list:
        return payload if isinstance(payload, list) else (payload or {}).get("items", [])

    def get_task(self, task_id: int) -> dict | None:
        try:
            return self._request("GET", f"/tasks/{task_id}")
        except requests.HTTPError as error:
            if error.response is not None and error.response.status_code in (403, 404):
                return None
            raise

    def get_kanban(self, project_id: int) -> tuple[int, dict[str, int], dict[int, int]]:
        """Return (view id, bucket id by title, bucket id by task id) for a project's first kanban view."""
        if project_id not in self._kanban:
            views = self._items(self._request("GET", f"/projects/{project_id}/views"))
            kanban = next((v for v in views if v["view_kind"] == "kanban"), None)
            if kanban is None:
                raise LookupError(f"project {project_id} has no kanban view")
            buckets = self._items(self._request("GET", f"/projects/{project_id}/views/{kanban['id']}/buckets/tasks"))
            by_title = {b["title"]: b["id"] for b in buckets}
            by_task = {t["id"]: b["id"] for b in buckets for t in b.get("tasks") or []}
            self._kanban[project_id] = (kanban["id"], by_title, by_task)
        return self._kanban[project_id]

    def move_task(self, project_id: int, view_id: int, bucket_id: int, task_id: int) -> None:
        self._request(
            "PUT",
            f"/projects/{project_id}/views/{view_id}/buckets/{bucket_id}/tasks",
            json={"task_id": task_id},
        )
        self._kanban[project_id][2][task_id] = bucket_id

    def get_comment_texts(self, task_id: int) -> list[str]:
        return [c["comment"] for c in self._items(self._request("GET", f"/tasks/{task_id}/comments"))]

    def add_comment(self, task_id: int, html: str) -> None:
        self._request("POST", f"/tasks/{task_id}/comments", json={"comment": html})


def sync_task(client: VikunjaClient, task_id: int, pulls: list[PullRequest], dry_run: bool) -> None:
    task = client.get_task(task_id)
    if task is None:
        logger.warning("vikunja#%d not found (referenced by %s)", task_id, ", ".join(f"{p.repo}#{p.number}" for p in pulls))
        return
    project_id = task["project_id"]
    view_id, bucket_by_title, bucket_by_task = client.get_kanban(project_id)

    target = choose_bucket([p.state for p in pulls])
    target_id = bucket_by_title.get(target)
    if target_id is None:
        logger.warning("vikunja#%d: project %d has no %r bucket; skipping", task_id, project_id, target)
        return
    if bucket_by_task.get(task_id) != target_id:
        logger.info("vikunja#%d %r -> %s", task_id, task["title"], target)
        if not dry_run:
            client.move_task(project_id, view_id, target_id, task_id)

    comments = client.get_comment_texts(task_id)
    for pull in pulls:
        if any(pull.url in text for text in comments):
            continue
        logger.info("vikunja#%d: comment link to %s#%d", task_id, pull.repo, pull.number)
        if not dry_run:
            client.add_comment(task_id, f'<p>PR <a href="{pull.url}">{pull.repo}#{pull.number}</a>: {pull.title}</p>')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="log what would change without changing it")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    repos = [r.strip() for r in os.environ["REPOS"].split(",") if r.strip()]
    since = datetime.now(UTC) - timedelta(days=int(os.environ.get("LOOKBACK_DAYS", "7")))

    github = requests.Session()
    github.headers.update(
        {
            "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
    )
    pulls = [pull for repo in repos for pull in fetch_pulls(github, repo, since)]
    by_task = group_by_task(pulls)
    logger.info("%d PRs read from %d repos; %d reference a task", len(pulls), len(repos), sum(1 for p in pulls if p.task_ids))

    client = VikunjaClient(os.environ["VIKUNJA_URL"], os.environ["VIKUNJA_TOKEN"])
    failed = 0
    for task_id, task_pulls in sorted(by_task.items()):
        try:
            sync_task(client, task_id, task_pulls, args.dry_run)
        except (requests.RequestException, LookupError) as error:
            failed += 1
            logger.error("vikunja#%d: %s", task_id, error)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
