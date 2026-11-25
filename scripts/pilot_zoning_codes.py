#!/usr/bin/env python3
"""Pilot GIS sample for Taoyuan old town. Diagnostics ONLY, no zoning claims.

Uses municipal ArcGIS layer 0, queries a small WGS84 bounding rectangle, and
outputs unique code samples to help decode AA fields. No addresses, targets, or
issues published. Restrict area and limit returned records.
"""
import collections
import datetime as dt
import json
import os
from pathlib import Path
import urllib.parse
import urllib.request

ENDPOINT = "https://3dmap.tycg.gov.tw/arcgis/rest/services/" + urllib.parse.quote("都市計畫使用分區") + "/MapServer/0/query"
OUT = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "commercial-zoning-pilot.json"
BBOX = (121.292, 24.978, 121.321, 25.007)  # test window only, NOT verified district boundary

def request(query):
    url = ENDPOINT+"?"+urllib.parse.urlencode(query)
    req = urllib.request.Request(url, headers={"User-Agent":"TaoyuanLandRadarPilot/0.5","Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=35) as r:
        data=json.load(r)
    if "error" in data:
        raise RuntimeError(str(data["error"])[:350])
    return data

def main():
    timestamp=dt.datetime.now(dt.timezone.utc).isoformat()
    report={"timestamp":timestamp,"bbox_wgs84":BBOX,
            "status":"schema_audit_only_not_verified",
            "warning":"Geographic window is not administrative boundary. AA codes not confirmed. Not a legal zoning certification.",
            "published_targets":0}
    try:
        common={"f":"json","geometry":",".join(map(str,BBOX)),
                "geometryType":"esriGeometryEnvelope","inSR":"4326",
                "spatialRel":"esriSpatialRelIntersects","where":"1=1"}
        count=request({**common,"returnCountOnly":"true"}).get("count")
        report["intersecting_polygon_count"]=count
        sample=request({**common,"outFields":"OBJECTID,AA05,AA06,AA08,AA45,AA46,TYPE",
                        "returnGeometry":"false","resultRecordCount":"150"})
        features=sample.get("features",[])
        report["retrieved_sample_count"]=len(features)
        report["transfer_limit_exceeded"]=sample.get("exceededTransferLimit",False)
        for field in ("AA05","AA06","AA08","AA45","AA46","TYPE"):
            c=collections.Counter(str(f.get("attributes",{}).get(field,"")).strip() for f in features)
            report["unique_"+field]=c.most_common(25)
        report["sample_objects"]=[f.get("attributes",{}) for f in features[:8]]
        report["status"]="sample_obtained_codes_still_unverified"
        print("PILOT_SUMMARY:",json.dumps(report,ensure_ascii=False)[:12500])
    except Exception as exc:
        report["status"]="pilot_error";report["error"]=str(exc)
        print("PILOT_ERROR:",str(exc)[:350])
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print("No target publishing; all records require municipal zoning-code confirmation.")

if __name__=="__main__":
    main()
