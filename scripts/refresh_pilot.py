#!/usr/bin/env python3
"""Refresh provisional Taoyuan pilot leads from public map UI and OSM.

The municipal same-host requests mirror public map lookups. Raw cadastral,
zoning, and OSM geometry stays in memory; the output remains pending review.
"""
import argparse
import datetime as dt
import hashlib
import http.cookiejar
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

from pyproj import Transformer
from shapely import wkt
from shapely.geometry import mapping, shape
from shapely.ops import transform

from pilot_scout import build

MAP_BASE = "https://urplanning.tycg.gov.tw/gisMap/"
OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://ovp.dresel.systems/api-as/interpreter",
)
PARCEL = {"section": "0002", "land": "00550001"}
TRANSFORM = Transformer.from_crs("EPSG:3826", "EPSG:4326", always_xy=True)


def official_session():
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    req = urllib.request.Request(MAP_BASE + "Map.aspx", headers={"User-Agent": "TaoyuanCommercialRadar/0.2", "Accept": "text/html"})
    with opener.open(req, timeout=25) as response:
        page = response.read(2_000_000).decode("utf-8", "replace")
    match = re.search(r'id=["\']hdToken["\'][^>]*value=["\']([^"\']+)', page)
    if not match:
        raise ValueError("Official map request token missing")
    return opener, match.group(1)


def official_query(opener, token, key, **fields):
    data = urllib.parse.urlencode({"key": key, "timeStamp": token, "timeName": "TWFwVG9rZW4=", **fields}).encode()
    req = urllib.request.Request(MAP_BASE + "ajax/datahandler.ashx", data=data, headers={
        "User-Agent": "TaoyuanCommercialRadar/0.2", "Referer": MAP_BASE + "Map.aspx",
        "Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"})
    with opener.open(req, timeout=30) as response:
        raw = response.read(2_000_000)
    result = json.loads(raw)
    if result.get("MSGCODE") != 200 or not result.get("DATA"):
        raise ValueError("Official map query failed: " + key)
    return result["DATA"], hashlib.sha256(raw).hexdigest()


def lonlat(wkt_string):
    geom = transform(TRANSFORM.transform, wkt.loads(wkt_string))
    if not geom.is_valid:
        repaired = geom.buffer(0)
        if geom.area <= 0 or abs(repaired.area - geom.area) / geom.area > 1e-6:
            raise ValueError("Official WKT changed area during topology repair")
        geom = repaired
    if geom.is_empty or not geom.is_valid or geom.geom_type not in ("Polygon", "MultiPolygon"):
        raise ValueError("Invalid official WKT geometry")
    return geom


def fetch_official():
    opener, token = official_session()
    parcel_rows, parcel_hash = official_query(opener, token, "GetRegionBySectLand", sect=PARCEL["section"], land=PARCEL["land"])
    if len(parcel_rows) != 1 or parcel_rows[0].get("section") != PARCEL["section"] or parcel_rows[0].get("parno") != "0055-0001":
        raise ValueError("Official cadastral anchor did not match 55-1")
    parcel_geom = lonlat(parcel_rows[0]["wktcadas"])
    parcel = {"type": "FeatureCollection", "features": [{"type": "Feature",
              "properties": {"LANDNO8": PARCEL["land"], "section": PARCEL["section"]},
              "geometry": mapping(parcel_geom)}]}
    use_rows, use_hash = official_query(opener, token, "GetUsezoneBySectLand", sect=PARCEL["section"], land=PARCEL["land"])
    if not any(row.get("zone_name") == "商業區" for row in use_rows):
        raise ValueError("Official map no longer reports commercial zone at 55-1")
    commercial_rows, commercial_hash = official_query(opener, token, "GetDistSectLandUseByAreaFilter",
        maxArea="1000000", minArea="0", dist="桃園區", sect="", uplanLanduse="商業區")
    if len(commercial_rows) != 1 or not commercial_rows[0].get("ContainWKT"):
        raise ValueError("Official map did not return the commercial distribution geometry")
    geometry = lonlat(commercial_rows[0]["ContainWKT"])
    if not geometry.covers(parcel_geom.centroid):
        raise ValueError("Official commercial distribution does not cover anchor parcel")
    parts = list(geometry.geoms) if geometry.geom_type == "MultiPolygon" else [geometry]
    zones = {"type": "FeatureCollection", "features": [{"type": "Feature",
             "properties": {"LANDUSE": "商業區", "district": "桃園區", "source_method": "official_map_distribution_query"},
             "geometry": mapping(part)} for part in parts]}
    selected = next(row for row in use_rows if row.get("zone_name") == "商業區")
    metadata = {"map_url": MAP_BASE + "Map.aspx", "district": "桃園區", "zone": "商業區",
                "anchor_section": PARCEL["section"], "anchor_land": PARCEL["land"],
                "plan_name": selected.get("urbanzonename"), "plan_reference": selected.get("urban_name"),
                "plan_pdf": selected.get("PDF"), "plan_map": selected.get("PIC"),
                "plan_publish_field": selected.get("publish"),
                "parcel_response_sha256": parcel_hash, "usezone_response_sha256": use_hash,
                "commercial_response_sha256": commercial_hash,
                "commercial_polygon_count": len(parts),
                "legal_verification": "pending_effective_plan_and_reuse_review"}
    return zones, parcel, metadata


def fetch_osm(anchor, radius_m=350):
    lat, lon = anchor.y, anchor.x
    south, north = lat - radius_m / 111000, lat + radius_m / 111000
    west, east = lon - radius_m / 101000, lon + radius_m / 101000
    query = f'[out:json][timeout:45];way["building"]({south:.7f},{west:.7f},{north:.7f},{east:.7f});out geom;'
    errors = []
    for endpoint in OVERPASS_ENDPOINTS:
        try:
            req = urllib.request.Request(endpoint, data=urllib.parse.urlencode({"data": query}).encode(), headers={
                "User-Agent": "TaoyuanCommercialRadar/0.2 (bounded public pilot)", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=65) as response:
                raw = response.read(8_000_000)
            data = json.loads(raw)
            if "elements" not in data or data.get("remark"):
                raise ValueError("OSM building query incomplete or failed")
            if len(data["elements"]) < 20:
                raise ValueError("OSM pilot response unexpectedly small")
            return data, {"endpoint": endpoint, "query": query, "response_sha256": hashlib.sha256(raw).hexdigest(),
                          "osm_timestamp": data.get("osm3s", {}).get("timestamp_osm_base"),
                          "license": "ODbL; © OpenStreetMap contributors", "prior_endpoint_errors": errors}
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append({"endpoint": endpoint, "error": str(exc)[:160]})
    raise ValueError("All OSM building endpoints failed: " + json.dumps(errors, ensure_ascii=False))


def refresh(red_scope, output, report_path):
    status = {"checked_at": dt.datetime.now(dt.timezone.utc).isoformat(),
              "status": "failed_closed", "published_official_targets": 0}
    try:
        zones, parcel, official_meta = fetch_official()
        anchor = shape(parcel["features"][0]["geometry"]).centroid
        osm, osm_meta = fetch_osm(anchor)
        red = json.loads(Path(red_scope).read_text(encoding="utf-8"))
        _, candidates = build(zones, parcel, osm, red)
        # The scout engine's standalone default points at the direct ArcGIS
        # layer. This refresh used the public city map's same-host queries.
        candidates["anchor_source"] = official_meta["map_url"]
        candidates["municipal_source"] = official_meta["map_url"]
        candidates["official_query"] = official_meta
        candidates["osm_query"] = osm_meta
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text(json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8")
        status.update({"status": "provisional_candidates_updated", "candidate_count": candidates["candidate_count"],
                       "official_source": official_meta["map_url"], "osm_source": osm_meta["endpoint"]})
        return status
    except Exception as exc:
        status["error"] = str(exc)[:300]
        raise
    finally:
        Path(report_path).parent.mkdir(parents=True, exist_ok=True)
        Path(report_path).write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--red-scope", default="docs/pilot_red_draft.geojson")
    p.add_argument("--output", required=True)
    p.add_argument("--report", required=True)
    args = p.parse_args()
    print(json.dumps(refresh(args.red_scope, args.output, args.report), ensure_ascii=False))


if __name__ == "__main__":
    main()
