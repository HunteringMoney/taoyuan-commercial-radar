#!/usr/bin/env python3
"""Generate FIELD-SURVEY leads from verified commercial polygons and building footprints.

INPUTS:
  --commercial: GeoJSON produced by validate_official_commercial_boundary.py
  --buildings: legally obtained GeoJSON building outlines, EPSG:4326
  --output: scout_candidates.json (never docs/targets.json)
No parcel, age, consent, legal qualification or official site verification is inferred.
Buildings spanning a zoning edge are excluded. Missing inputs fail closed.
"""
import argparse
import datetime as dt
import json
import math
from pathlib import Path
from shapely.geometry import shape, mapping, Point
from shapely.ops import transform, unary_union
from shapely.strtree import STRtree

def load(path):
    data=json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("type")!="FeatureCollection" or not isinstance(data.get("features"),list):
        raise ValueError("Expected GeoJSON FeatureCollection")
    return data["features"]

def check_poly(feature):
    geom=shape(feature.get("geometry"))
    if geom.is_empty or not geom.is_valid or geom.geom_type not in ("Polygon","MultiPolygon"):
        raise ValueError("Invalid polygon geometry")
    return geom

def xy_to_meters(g):
    # Local equirectangular approximation: topology in WGS84, grouping in metres.
    # Not for legal boundary measurements or development site area.
    return transform(lambda x,y,z=None:(x*101000,y*111000),g)

def discover(commercial, buildings, min_buildings=3, gap_m=8):
    if not commercial:
        return []
    zones=[]
    for f in commercial:
        if (f.get("properties") or {}).get("verified_zoning_geometry") is not True:
            raise ValueError("Commercial input is not verified by the boundary validator")
        if (f.get("properties") or {}).get("使用分區") not in (
            "商業區","第一種商業區","第二種商業區","第三種商業區","第四種商業區"):
            raise ValueError("Non-commercial zoning encountered")
        zones.append(check_poly(f))
    boundary=unary_union(zones)
    footprints=[]
    for f in buildings:
        g=check_poly(f)
        # Fail closed on boundary crossings: centroid alone is not enough.
        if boundary.covers(g):
            footprints.append(g)
    if not footprints:
        return []
    metric=[xy_to_meters(g) for g in footprints]
    buffered=[g.buffer(gap_m/2) for g in metric]
    tree=STRtree(buffered)
    parent=list(range(len(buffered)))
    def root(i):
        while i!=parent[i]:
            parent[i]=parent[parent[i]]
            i=parent[i]
        return i
    def union(i,j):
        a,b=root(i),root(j)
        if a!=b:parent[b]=a
    for i,g in enumerate(buffered):
        for j in tree.query(g):
            j=int(j)
            if j>i and g.intersects(buffered[j]):
                union(i,j)
    groups={}
    for i in range(len(footprints)):
        groups.setdefault(root(i),[]).append(i)
    found=[]
    for indices in groups.values():
        if len(indices)<min_buildings:continue
        merged=unary_union([footprints[i] for i in indices])
        p=merged.representative_point()
        # Footprint area is NOT lot or developable area.
        built_area_m2=round(sum(metric[i].area for i in indices),1)
        found.append({
            "id":"scout-"+str(len(found)+1).zfill(3),
            "latitude":round(p.y,7),"longitude":round(p.x,7),
            "building_footprint_count":len(indices),
            "approx_total_roof_footprint_m2":built_area_m2,
            "status":"screening_only_field_review_required",
            "zone_basis":"official polygons checked by upstream validator",
            "reason":"相鄰建物輪廓集中，值得現場確認屋齡、道路與地號",
            "disclaimer":"非土地面積、非地籍基地、非危老資格或開發可行性認證"
        })
    return sorted(found,key=lambda x:(-x["building_footprint_count"],-x["approx_total_roof_footprint_m2"]))

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--commercial",required=True)
    p.add_argument("--buildings",required=True)
    p.add_argument("--output",required=True)
    p.add_argument("--min-buildings",type=int,default=3)
    args=p.parse_args()
    if args.min_buildings<2:raise ValueError("min-buildings must be >=2")
    leads=discover(load(args.commercial),load(args.buildings),args.min_buildings)
    out={"generated_at":dt.datetime.now(dt.timezone.utc).isoformat(),
         "district":"桃園區","allowed_zone":"商業區",
         "verification_status":"screening_leads_not_official_targets",
         "input_commercial":args.commercial,"input_buildings":args.buildings,
         "candidate_count":len(leads),"targets":leads}
    Path(args.output).parent.mkdir(parents=True,exist_ok=True)
    Path(args.output).write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    print("Field-inspection leads:",len(leads),"(not official verified development targets)")
if __name__=="__main__":main()
