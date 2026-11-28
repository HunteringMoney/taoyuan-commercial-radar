#!/usr/bin/env python3
"""Publish only provisional lead JSON and refresh status to GitHub Pages docs.

Never writes docs/targets.json or marks a lead as a verified development site.
"""
import argparse
import json
from pathlib import Path


def sync(result_path, report_path, docs_dir):
    docs = Path(docs_dir)
    docs.mkdir(parents=True, exist_ok=True)
    report_file = Path(report_path)
    report = json.loads(report_file.read_text(encoding="utf-8")) if report_file.exists() else {
        "status": "failed_closed", "error": "pilot refresh did not produce a report", "checked_at": None}
    status = {"checked_at": report.get("checked_at"), "status": report.get("status"),
              "candidate_count": report.get("candidate_count"),
              "official_verified_targets": 0, "error": report.get("error")}
    existing = docs / "pilot_scout_candidates.json"
    if existing.exists():
        try:
            status["last_candidate_generated_at"] = json.loads(existing.read_text(encoding="utf-8")).get("generated_at")
        except (ValueError, OSError):
            status["last_candidate_generated_at"] = None
    if report.get("status") == "provisional_candidates_updated":
        candidate_file = Path(result_path)
        if not candidate_file.exists():
            raise ValueError("Successful refresh has no candidate output")
        data = json.loads(candidate_file.read_text(encoding="utf-8"))
        leads = data.get("targets")
        if not isinstance(leads, list) or data.get("candidate_count") != len(leads):
            raise ValueError("Candidate count mismatch")
        if data.get("status") != "provisional_real_location_leads_pending_verification":
            raise ValueError("Candidate output has wrong verification state")
        for lead in leads:
            if lead.get("legal_zone_verified") is not False or lead.get("parcel_no") is not None or lead.get("building_age") is not None:
                raise ValueError("Candidate wrongly claims legal zoning, parcel, or age")
            if lead.get("status") != "pending_official_zoning_and_field_review":
                raise ValueError("Candidate is missing pending-review status")
        existing.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        status["last_candidate_generated_at"] = data.get("generated_at")
    (docs / "pilot_refresh_status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return status


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--result", required=True)
    p.add_argument("--report", required=True)
    p.add_argument("--docs", required=True)
    a = p.parse_args()
    print(json.dumps(sync(a.result, a.report, a.docs), ensure_ascii=False))


if __name__ == "__main__":
    main()
