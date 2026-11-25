#!/usr/bin/env python3
"""Inspect official Taoyuan urban planning GIS safely. No target publishing.

Output an Actions artifact with the actual source metadata and a very small
sample query, enabling subsequent development against verified schema.
Never infer land-use zoning from map color, OSM tags, or address alone.
"""
import datetime as dt
import json
import os
from pathlib import Path
import urllib.parse
import urllib.request

BASE = "https://3dmap.tycg.gov.tw/arcgis/rest/services/" + urllib.parse.quote("都市計畫使用分區") + "/MapServer"
OUT = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "taoyuan-official-gis-diagnostic.json"

def fetch(url, params=None):
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "TaoyuanCommercialRadar/0.4 (+public GIS audit)", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=22) as response:
        if response.status != 200:
            raise RuntimeError("HTTP " + str(response.status))
        payload = response.read(1024 * 1024)
    data = json.loads(payload)
    if "error" in data:
        raise RuntimeError(str(data["error"])[:300])
    return data

def run():
    report = {"checked_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
              "service": BASE, "status": "not_verified",
              "candidate_count": 0, "published_targets": 0}
    try:
        service = fetch(BASE, {"f": "json"})
        report["service_name"] = service.get("mapName")
        report["layers"] = [{"id": l.get("id"), "name": l.get("name")}
                            for l in service.get("layers", [])[:30]]
        report["layer_details"] = []
        for layer in service.get("layers", [])[:5]:
            lid = layer.get("id")
            detail = fetch(f"{BASE}/{lid}", {"f": "json"})
            fields = [{"name": f.get("name"), "alias": f.get("alias"),
                       "type": f.get("type")} for f in detail.get("fields", [])]
            item = {"id": lid, "name": layer.get("name"),
                    "geometryType": detail.get("geometryType"),
                    "fields": fields,
                    "supportsQuery": "Query" in (detail.get("capabilities") or ""),
                    "spatialReference": detail.get("extent", {}).get("spatialReference", {}),
                    "source_license": detail.get("copyrightText", "")}
            # Small sample to inspect classifications. Do NOT publish or infer zoning.
            if item["supportsQuery"]:
                try:
                    sample = fetch(f"{BASE}/{lid}/query", {
                        "f": "json", "where": "1=1", "outFields": "*",
                        "returnGeometry": "false", "resultRecordCount": 3
                    })
                    item["sample_attributes"] = [x.get("attributes", {}) for x in sample.get("features", [])]
                except Exception as exc:
                    item["sample_error"] = str(exc)[:300]
            report["layer_details"].append(item)
        report["status"] = "metadata_readable_not_zoning_verified"
        print("GIS metadata successfully retrieved. Zoning field and district boundary require validation before scanning.")
    except Exception as exc:
        report["status"] = "source_unavailable"
        report["error"] = str(exc)[:400]
        print("GIS connectivity/schema discovery blocked; no targets will be generated:", report["error"])
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Diagnostic:", OUT, "status:", report["status"])
    print("SCHEMA_SUMMARY:", json.dumps({"layers": report.get("layers", []), "layer_details": report.get("layer_details", [])}, ensure_ascii=False)[:12000])
    print("Never publish unknown/unchecked records to docs/targets.json.")

if __name__ == "__main__":
    run()
