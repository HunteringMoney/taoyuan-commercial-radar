#!/usr/bin/env python3
"""Notify only for new, explicitly verified commercial-zone targets.

No external Python dependencies. Fail closed on missing/incomplete verification.
The upstream producer must perform independent official GIS checks; this notifier
does not independently verify zoning merely because a record claims verification.
"""
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://api.github.com"
REPO = os.environ.get("GITHUB_REPOSITORY", "")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
DATA = Path(__file__).resolve().parents[1] / "docs" / "targets.json"
SOURCE_HOSTS = {"urplanning.tycg.gov.tw", "3dmap.tycg.gov.tw"}
MARKER = "<!-- taoyuan-commercial-target:"
REQUIRED = ("id", "address", "district", "zone", "official_zoning_verified",
            "official_source_url", "official_verified_at", "verification_method")

def api(method, path, payload=None):
    if not REPO or not TOKEN:
        raise RuntimeError("GITHUB_REPOSITORY / GITHUB_TOKEN missing")
    url = BASE + path
    data = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
    headers = {"Authorization": "Bearer " + TOKEN,
               "Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28",
               "User-Agent": "taoyuan-commercial-radar"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    with urllib.request.urlopen(urllib.request.Request(
            url, headers=headers, data=data, method=method), timeout=25) as response:
        return json.load(response)

def validated(item):
    if not isinstance(item, dict) or any(k not in item for k in REQUIRED):
        return False
    if item["district"] != "桃園區" or item["zone"] != "商業區":
        return False
    if item["official_zoning_verified"] is not True:
        return False
    if item.get("verification_method") not in ("official_gis_manual", "official_gis_api"):
        return False
    if not all(isinstance(item[k], str) and item[k].strip() for k in
               ("id", "address", "official_source_url", "official_verified_at")):
        return False
    u = urllib.parse.urlparse(item["official_source_url"])
    if u.scheme != "https" or u.hostname not in SOURCE_HOSTS:
        return False
    if not item["official_verified_at"].startswith("20"):
        return False
    # An upstream verifier must set this only after independently checking
    # the official zoning map, not from address text or OSM land-use guesses.
    if item.get("review_status") != "approved":
        return False
    return True

def existing_marker_ids():
    found = set()
    page = 1
    while True:
        issues = api("GET", f"/repos/{REPO}/issues?state=all&per_page=100&page={page}")
        for issue in issues:
            body = issue.get("body") or ""
            offset = body.find(MARKER)
            if offset >= 0:
                end = body.find(" -->", offset)
                if end >= 0:
                    found.add(body[offset + len(MARKER):end])
        if len(issues) < 100:
            break
        page += 1
        if page > 30:
            raise RuntimeError("Too many issues to ensure deduplication; stop rather than duplicate notifications")
    return found

def main():
    data = json.loads(DATA.read_text(encoding="utf-8"))
    if data.get("verification_status") != "official_zoning_verified":
        print("SAFE STOP: official zoning dataset not connected/verified; no notifications.")
        return
    all_targets = data.get("targets")
    if not isinstance(all_targets, list):
        raise ValueError("targets must be a list")
    approved = [x for x in all_targets if validated(x)]
    print(f"Total: {len(all_targets)}, eligible: {len(approved)}; rejected: {len(all_targets)-len(approved)}")
    if not approved:
        print("No verified new targets; no issues created.")
        return
    seen = existing_marker_ids()
    created = 0
    for item in approved:
        digest = hashlib.sha256(item["id"].encode()).hexdigest()[:20]
        if digest in seen:
            continue
        body = (f"{MARKER}{digest} -->\n"
                f"## 新開發目標（已通過資料審核）\n\n"
                f"- **位置：** {item['address']}\n"
                f"- **行政區／都市計畫分區：** 桃園區／商業區\n"
                f"- **官方圖資：** {item['official_source_url']}\n"
                f"- **官方分區核對日期：** {item['official_verified_at']}\n"
                f"- **核對方式：** {item['verification_method']}\n"
                f"- **建議現勘理由：** {item.get('reason','需實地查核')}\n\n"
                "此通知代表該筆資料通過上游資料核對標記與審核，不代表危老資格、"
                "建築線、地籍權屬或地主意願已確認。請回官方圖資複查。\n")
        api("POST", f"/repos/{REPO}/issues", {
            "title": f"【土地獵人】桃園商業區新目標｜{item['address'][:65]}",
            "body": body
        })
        seen.add(digest)
        created += 1
    print(f"Created {created} new notification issue(s).")

if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, urllib.error.URLError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
