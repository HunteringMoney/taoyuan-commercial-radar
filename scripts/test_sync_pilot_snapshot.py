import json
import tempfile
import unittest
from pathlib import Path

from sync_pilot_snapshot import sync


class SnapshotTests(unittest.TestCase):
    def test_failed_refresh_preserves_last_candidate(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            docs = root / "docs"
            docs.mkdir()
            prior = {"generated_at": "2026-11-27T00:00:00Z", "targets": []}
            (docs / "pilot_scout_candidates.json").write_text(json.dumps(prior))
            report = root / "report.json"
            report.write_text(json.dumps({"status": "failed_closed", "checked_at": "2026-11-28T00:00:00Z", "error": "source unavailable"}))
            status = sync(root / "missing.json", report, docs)
            self.assertEqual(json.loads((docs / "pilot_scout_candidates.json").read_text()), prior)
            self.assertEqual(status["last_candidate_generated_at"], prior["generated_at"])
            self.assertEqual(status["status"], "failed_closed")

    def test_unverified_lead_is_saved_but_verified_claim_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            docs = root / "docs"
            report = root / "report.json"
            report.write_text(json.dumps({"status": "provisional_candidates_updated", "checked_at": "2026-11-28T00:00:00Z", "candidate_count": 1}))
            output = root / "candidates.json"
            lead = {"status": "pending_official_zoning_and_field_review", "legal_zone_verified": False,
                    "parcel_no": None, "building_age": None}
            data = {"status": "provisional_real_location_leads_pending_verification",
                    "generated_at": "2026-11-28T00:00:00Z", "candidate_count": 1, "targets": [lead]}
            output.write_text(json.dumps(data))
            sync(output, report, docs)
            self.assertEqual(json.loads((docs / "pilot_scout_candidates.json").read_text())["targets"], [lead])
            lead["legal_zone_verified"] = True
            output.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                sync(output, report, docs)


if __name__ == "__main__":
    unittest.main()
