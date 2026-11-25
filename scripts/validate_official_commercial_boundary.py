#!/usr/bin/env python3
"""Validate a LEGITIMATELY OBTAINED municipal commercial-zoning GeoJSON.

This program NEVER derives legal land use from OSM, map colors, AA code guesses,
building heights, land use statistics, or positional samples. It publishes only
when an operator supplies an official zoning polygon dataset with documented
provenance and a separately sourced official Taoyuan district boundary.

Requires pip install shapely>=2.0. Validated output is for further manual QA,
not a zoning certificate and NOT an automatic candidate/Issue notification.
"""
import argparse
import datetime
import json
from pathlib import Path
from urllib.parse import urlparse
from shapely.geometry import shape, mapping
from shapely.ops import unary_union
from shapely.validation import explain_validity

ALLOWED_HOSTS={"urplanning.tycg.gov.tw","urdb.tycg.gov.tw","oba.tycg.gov.tw","data.tycg.gov.tw","opendata.tycg.gov.tw"}
ZONING_LABELS={"商業區","第一種商業區","第二種商業區","第三種商業區","第四種商業區"}
def url_is_official(url):
    try:
        u=urlparse(url)
        return u.scheme=="https" and u.hostname in ALLOWED_HOSTS
    except (TypeError, ValueError): return False
def read_fc(path):
    d=json.loads(Path(path).read_text(encoding="utf-8"))
    if d.get("type")!="FeatureCollection" or not isinstance(d.get("features"),list):
        raise ValueError("Expected GeoJSON FeatureCollection")
    return d
def source_check(meta):
    for k in ("plan_name","legal_announcement_date","source_url","source_agency",
              "boundary_source_url","boundary_version","zoning_version","license_reviewed"):
        if not meta.get(k): raise ValueError("Missing official provenance field: "+k)
    if not url_is_official(meta["source_url"]):
        raise ValueError("Zoning source is not documented as official Taoyuan source")
    if meta.get("source_agency")!="桃園市政府都市發展局":
        raise ValueError("Source agency must be verified explicitly")
    if meta.get("license_reviewed") is not True:
        raise ValueError("Source licensing/manual approval required")
    if meta.get("operator_approved") is not True:
        raise ValueError("Explicit approval after checking official zoning plan required")
    # Avoid silently assuming ambiguous shapefile coordinates are WGS84.
    if meta.get("crs")!="EPSG:4326":
        raise ValueError("GeoJSON must be verified/reprojected to EPSG:4326")
def accept(zoning, district, meta):
    source_check(meta)
    boundaries=[]
    for feat in district["features"]:
        p=feat.get("properties") or {}
        if p.get("COUNTY")!="桃園市" or p.get("TOWN")!="桃園區":
            continue
        geom=shape(feat["geometry"])
        if not geom.is_valid or geom.is_empty: raise ValueError("Invalid district boundary")
        boundaries.append(geom)
    if len(boundaries)!=1: raise ValueError("Require exactly one authoritative Taoyuan district polygon")
    boundary=boundaries[0]
    accepted=[];rejected={"other_zone":0,"other_district":0,"crosses_district":0,"invalid_geometry":0,"missing_zone":0}
    for feat in zoning["features"]:
        props=feat.get("properties") or {}
        zone=str(props.get("使用分區") or "").strip()
        if not zone: rejected["missing_zone"]+=1;continue
        if zone not in ZONING_LABELS: rejected["other_zone"]+=1;continue
        geom=shape(feat["geometry"])
        if geom.geom_type not in ("Polygon","MultiPolygon") or geom.is_empty or not geom.is_valid:
            rejected["invalid_geometry"]+=1;continue
        if not boundary.intersects(geom):
            rejected["other_district"]+=1;continue
        # Fail closed: don't truncate cross-boundary polygons without manual review
        if not boundary.covers(geom):
            rejected["crosses_district"]+=1;continue
        accepted.append({"type":"Feature","properties":{"使用分區":zone,"source_url":meta["source_url"],"plan_name":meta["plan_name"],"verified_zoning_geometry":True},"geometry":mapping(geom)})
    result={"type":"FeatureCollection","features":accepted}
    report={"checked_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "status":"passed_geometry_rules_pending_field_review",
            "accepted":len(accepted),"rejected":rejected,"source_url":meta["source_url"],
            "note":"This is a geometry and documented-source gate, not a substitute for original municipal plan verification or zoning certificate. Never publish target Issues directly."}
    return result,report
def main():
    a=argparse.ArgumentParser();a.add_argument("--zoning",required=True);a.add_argument("--district",required=True);a.add_argument("--metadata",required=True);a.add_argument("--output",required=True);a.add_argument("--report",required=True);ns=a.parse_args()
    zones=read_fc(ns.zoning);district=read_fc(ns.district)
    meta=json.loads(Path(ns.metadata).read_text(encoding="utf-8"))
    out,report=accept(zones,district,meta)
    Path(ns.output).write_text(json.dumps(out,ensure_ascii=False),encoding="utf-8")
    Path(ns.report).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False))
if __name__=="__main__":main()
