#!/usr/bin/env python3
"""GitHub Expensify/App -> Telegram notifier.

Polls Expensify/App for:
  1) Comments that @-mention you (C+ approvals, proposal replies, generic mentions).
  2) Issues newly assigned to you.

State is persisted in state.json (committed back to the repo by the workflow)
so we never send duplicate notifications.

Required env vars:
  GITHUB_USERNAME    your GitHub login (e.g. "alibaba")
  GH_TOKEN           a GitHub token (the workflow uses secrets.GITHUB_TOKEN)
  TELEGRAM_TOKEN     bot token from @BotFather
  TELEGRAM_CHAT_ID   your chat id with the bot
"""

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

# ---------------- Configuration ----------------

GITHUB_USERNAME = os.environ["GITHUB_USERNAME"]
GITHUB_TOKEN = os.environ.get("GH_TOKEN", "")
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

REPO = "Expensify/App"
STATE_FILE = Path("state.json")
INITIAL_LOOKBACK_HOURS = 6  # on first run, look back this many hours

GITHUB_API = "https://api.github.com"
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


# ---------------- State ----------------

def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    lookback = datetime.now(timezone.utc) - timedelta(hours=INITIAL_LOOKBACK_HOURS)
    return {
        "initialized": False,
        "last_comment_check": lookback.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "known_assignments": [],
        "notified_ids": [],
    }


def save_state(state):
    # keep notified_ids bounded so the file doesn't grow forever
    state["notified_ids"] = state["notified_ids"][-1000:]
    STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True))


# ---------------- HTTP helpers ----------------

def gh_headers():
    h = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": f"{GITHUB_USERNAME}-expensify-notifier",
    }
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h


def gh_paginated(url, params=None, max_pages=20):
    params = dict(params or {})
    params.setdefault("per_page", 100)
    pages = 0
    while url and pages < max_pages:
        r = requests.get(url, headers=gh_headers(), params=params, timeout=30)
        r.raise_for_status()
        for item in r.json():
            yield item
        url = r.links.get("next", {}).get("url")
        params = None  # link URL already has params baked in
        pages += 1


def escape_html(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def send_telegram(text):
    url = f"{TELEGRAM_API}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        r = requests.post(url, json=payload, timeout=15)
        if not r.ok:
            print(f"[telegram] {r.status_code}: {r.text}", file=sys.stderr)
    except requests.RequestException as e:
        print(f"[telegram] exception: {e}", file=sys.stderr)


# ---------------- Comment classification ----------------

def classify_comment(body):
    """Best-effort label for what kind of comment this is."""
    if not body:
        return ("Mention", "🔔")
    b = body.lower()
    if "c+ reviewed" in b or "🎀" in body:
        return ("C+ reviewed your proposal", "✅")
    if "i'd like to propose" in b or "i would like to propose" in b:
        return ("You were proposed for this issue", "🎯")
    if re.search(r"proposal.{0,60}(looks good|approved|lgtm|accepted)", b):
        return ("Proposal approved", "👍")
    if re.search(r"(looks good to me|approved|lgtm)\b", b):
        return ("Approval / positive feedback", "👍")
    if "📣" in body:
        return ("Announcement / call-out", "📣")
    return ("Mention / reply", "💬")


# ---------------- Checks ----------------

def check_comments(state):
    """Find new comments anywhere in the repo that @-mention the user."""
    since = state["last_comment_check"]
    new_latest = since
    sent = 0

    url = f"{GITHUB_API}/repos/{REPO}/issues/comments"
    params = {"since": since, "sort": "created", "direction": "asc"}

    mention_re = re.compile(rf"@{re.escape(GITHUB_USERNAME)}\b", re.IGNORECASE)

    for comment in gh_paginated(url, params):
        created = comment.get("updated_at") or comment["created_at"]
        if created > new_latest:
            new_latest = created

        body = comment.get("body") or ""
        author = (comment.get("user") or {}).get("login", "")

        if author.lower() == GITHUB_USERNAME.lower():
            continue
        if not mention_re.search(body):
            continue

        key = f"comment:{comment['id']}"
        if key in state["notified_ids"]:
            continue

        label, emoji = classify_comment(body)
        issue_url = comment.get("issue_url", "")
        issue_number = issue_url.rsplit("/", 1)[-1] if issue_url else "?"
        html_url = comment.get("html_url", "")

        snippet = body.strip()
        if len(snippet) > 500:
            snippet = snippet[:500] + "…"

        msg = (
            f"{emoji} <b>{escape_html(label)}</b>\n"
            f"Issue <b>#{escape_html(issue_number)}</b> • by <b>{escape_html(author)}</b>\n\n"
            f"{escape_html(snippet)}\n\n"
            f'<a href="{html_url}">Open on GitHub ↗</a>'
        )
        send_telegram(msg)
        state["notified_ids"].append(key)
        sent += 1

    state["last_comment_check"] = new_latest
    return sent


def check_assignments(state):
    """Detect newly-assigned issues by diffing against last known set."""
    url = f"{GITHUB_API}/repos/{REPO}/issues"
    params = {"assignee": GITHUB_USERNAME, "state": "open", "per_page": 100}

    known = set(state.get("known_assignments", []))
    current = set()
    new_issues = []

    for issue in gh_paginated(url, params, max_pages=5):
        if "pull_request" in issue:
            continue  # skip PRs
        num = issue["number"]
        current.add(num)
        if num not in known:
            new_issues.append(issue)

    sent = 0
    # On the very first run we don't want to spam every currently-assigned
    # issue. We just snapshot them and start notifying on the next run.
    if state.get("initialized"):
        for issue in new_issues:
            num = issue["number"]
            title = issue.get("title", "")
            html_url = issue.get("html_url", "")
            labels = ", ".join(l["name"] for l in issue.get("labels", [])) or "—"

            msg = (
                f"📌 <b>You were assigned to an issue!</b>\n\n"
                f"<b>#{num}</b> {escape_html(title)}\n"
                f"Labels: {escape_html(labels)}\n\n"
                f'<a href="{html_url}">Open issue ↗</a>'
            )
            send_telegram(msg)
            sent += 1

    state["known_assignments"] = sorted(current)
    state["initialized"] = True
    return sent


# ---------------- Entrypoint ----------------

def main():
    state = load_state()
    print(
        f"[monitor] initialized={state.get('initialized')}, "
        f"last_comment_check={state['last_comment_check']}, "
        f"known_assignments={len(state.get('known_assignments', []))}"
    )

    sent_c = sent_a = 0
    try:
        sent_c = check_comments(state)
    except Exception as e:
        print(f"[monitor] comment check failed: {e}", file=sys.stderr)
    try:
        sent_a = check_assignments(state)
    except Exception as e:
        print(f"[monitor] assignment check failed: {e}", file=sys.stderr)
    finally:
        save_state(state)

    print(f"[monitor] sent {sent_c} comment notifs, {sent_a} assignment notifs")


if __name__ == "__main__":
    main()
