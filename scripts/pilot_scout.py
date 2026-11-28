#!/usr/bin/env python3
"""Build provisional, real-location building-group leads from two source exports.

Inputs are a live municipal zoning query and an OSM Overpass export. This does
not certify the current legal plan, cadastral site, age, or developability.
"""
import argparse
import datetime as dt
import json
from pathlib import Path

from shapely.geometry import Polygon, mapping, shape
from shapely.ops import unary_union

from candidate_discovery import discover, xy_to_meters

MUNICIPAL_URL = "https://urbandatasrv.tycg.gov.tw/server/rest/services/TY_UPGIS/TYMap_SDE/MapServer/2"
OSM_URL = "https://www.openstreetmap.org/copyright"


def build(zoning, parcel, osm, radius_m=350, min_buildings=3):
    if len(parcel.get("features", [])) != 1:
        raise ValueError("Expected exactly one official cadastral anchor polygon")
    anchor = shape(parcel["features"][0]["geometry"]).centroid
    if parcel["features"][0].get("properties", {}).get("LANDNO8") != "00550001":
        raise ValueError("Anchor parcel identifier mismatch")
    local_circle = xy_to_meters(anchor).buffer(radius_m)
    zones = []
    for feat in zoning.get("features", []):
        props = feat.get("properties") or {}
        if props.get("LANDUSE") != "商業區" or props.get("MUPLAN") != "桃園市都市計畫":
            continue
        geom = shape(feat["geometry"])
        if geom.is_valid and xy_to_meters(geom).intersects(local_circle):
            zones.append({"type": "Feature", "properties": {
                "使用分區": "商業區", "source_url": MUNICIPAL_URL,
                "zoning_status": "pending_plan_version_and_visual_crosscheck",
                "verified_zoning_geometry": False}, "geometry": mapping(geom)})
    if not zones:
        raise ValueError("No municipal commercial polygons by the anchor")
    boundary = unary_union([shape(f["geometry"]) for f in zones])
    buildings = []
    for element in osm.get("elements", []):
        if element.get("type") != "way" or "building" not in element.get("tags", {}):
            continue
        vertices = [(p["lon"], p["lat"]) for p in element.get("geometry", [])]
        if len(vertices) < 4 or vertices[0] != vertices[-1]:
            continue
        geom = Polygon(vertices)
        if not geom.is_valid or geom.area <= 0:
            continue
        if not local_circle.covers(xy_to_meters(geom)) or not boundary.covers(geom):
            continue
        buildings.append({"type": "Feature", "properties": {"osm_id": element["id"]}, "geometry": mapping(geom)})
    leads = discover(zones, buildings, min_buildings=min_buildings, zoning_verified=False)
    for lead in leads:
        lead["maps_url"] = "https://www.openstreetmap.org/?mlat={latitude}&mlon={longitude}#map=18/{latitude}/{longitude}".format(**lead)
        lead["building_source"] = "OpenStreetMap contributors (ODbL)"
        lead["building_source_url"] = OSM_URL
        lead["parcel_no"] = None
        lead["building_age"] = None
        lead["legal_zone_verified"] = False
    scope = {"type": "FeatureCollection", "features": zones}
    report = {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
              "status": "provisional_real_location_leads_pending_verification",
              "anchor_source": MUNICIPAL_URL.replace("/2", "/1"),
              "anchor_parcel": "桃園段中南小段 55-1",
              "anchor_centroid": [round(anchor.x, 8), round(anchor.y, 8)],
              "pilot_radius_m": radius_m, "municipal_source": MUNICIPAL_URL,
              "osm_source": OSM_URL, "osm_ways_in_export": len(osm.get("elements", [])),
              "commercial_polygons_selected": len(zones),
              "buildings_wholly_inside_commercial_and_radius": len(buildings),
              "candidate_count": len(leads), "targets": leads,
              "pending": ["Screenshot control-point registration", "Official plan effective version and zoning crosscheck", "Cadastral boundaries for each group", "Field review"]}
    return scope, report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--zoning", required=True)
    p.add_argument("--parcel", required=True)
    p.add_argument("--osm", required=True)
    p.add_argument("--scope-output", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--radius-m", type=float, default=350)
    p.add_argument("--min-buildings", type=int, default=3)
    a = p.parse_args()
    inputs = [json.loads(Path(x).read_text(encoding="utf-8")) for x in (a.zoning, a.parcel, a.osm)]
    scope, report = build(*inputs, radius_m=a.radius_m, min_buildings=a.min_buildings)
    Path(a.scope_output).parent.mkdir(parents=True, exist_ok=True)
    Path(a.output).parent.mkdir(parents=True, exist_ok=True)
    Path(a.scope_output).write_text(json.dumps(scope, ensure_ascii=False, indent=2), encoding="utf-8")
    Path(a.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("commercial_polygons_selected", "buildings_wholly_inside_commercial_and_radius", "candidate_count")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
