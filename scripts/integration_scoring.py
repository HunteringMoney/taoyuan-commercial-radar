"""Transparent triage rules for Taoyuan District commercial-zone redevelopment.

Scores are *screening priority* only, NOT estimates of actual construction
feasibility, urban renewal eligibility, ownership consent or profitability.
Only zone-confirmed candidates can be ranked for field inspection.
"""
from dataclasses import dataclass
from typing import Optional

@dataclass
class Candidate:
    name: str
    district: str
    zone: str
    official_zone_verified: bool
    area_m2: Optional[float] = None
    contiguous_building_count: Optional[int] = None
    low_rise_ratio: Optional[float] = None
    frontage_m: Optional[float] = None
    road_width_m: Optional[float] = None
    fragmented_lot_count: Optional[int] = None
    existing_redevelopment: Optional[bool] = None
    built_year_verified: bool = False

def score(candidate: Candidate):
    if candidate.district != "桃園區" or candidate.zone != "商業區" or not candidate.official_zone_verified:
        return {"eligible": False, "score": None, "grade": "排除或分區待確認",
                "reason": "必須先以官方都市計畫資料確認桃園區法定商業區"}
    if candidate.existing_redevelopment is True:
        return {"eligible": False, "score": None, "grade": "排除",
                "reason": "已知正在重建／新建的基地，暫不列入陌生開發"}
    pts, missing, reasons = 0, [], []
    def add(name, val, fn, maximum):
        nonlocal pts
        if val is None:
            missing.append(name)
        else:
            n = fn(val)
            pts += n
            reasons.append(f"{name}：{n}/{maximum} 分")

    # Policy weights total exactly 100; deliberately no guessing on missing.
    add("候選連續基地面積(m²)", candidate.area_m2,
        lambda x: 25 if x >= 1000 else 20 if x >= 600 else 14 if x >= 300 else 7 if x >= 150 else 0, 25)
    add("相鄰建物棟數", candidate.contiguous_building_count,
        lambda x: 20 if x >= 8 else 15 if x >= 5 else 9 if x >= 3 else 0, 20)
    add("低樓層建物比例", candidate.low_rise_ratio,
        lambda x: 20 if x >= .8 else 15 if x >= .6 else 8 if x >= .4 else 0, 20)
    add("可形成臨路面寬(m)", candidate.frontage_m,
        lambda x: 15 if x >= 20 else 10 if x >= 12 else 5 if x >= 6 else 0, 15)
    add("臨路寬度(m)", candidate.road_width_m,
        lambda x: 10 if x >= 8 else 6 if x >= 6 else 3 if x >= 4 else 0, 10)
    add("潛在需整合地號數", candidate.fragmented_lot_count,
        lambda x: 10 if 1 <= x <= 4 else 6 if x <= 8 else 2 if x <= 15 else 0, 10)
    # Unknown measurements are a caution, not a favorable assumption.
    if missing:
        grade = "資料不足，待查證"
    else:
        grade = "優先現勘" if pts >= 75 else "次優先現勘" if pts >= 55 else "低優先"
    return {"eligible": True, "score": pts, "grade": grade, "missing": missing,
            "reason": "；".join(reasons),
            "warning": "低矮≠老舊，建物輪廓≠地籍；建築線、屋齡、權屬、地主意願須另查"}

if __name__ == "__main__":
    a=Candidate("排除住宅區","桃園區","住宅區",True,1000,10,.9,20,10,3)
    assert not score(a)["eligible"]
    b=Candidate("未核對","桃園區","商業區",False,1000,10,.9,20,10,3)
    assert not score(b)["eligible"]
    c=Candidate("完整高分樣本","桃園區","商業區",True,1000,10,.9,20,10,3)
    assert score(c)["score"]==100 and score(c)["grade"]=="優先現勘"
    d=Candidate("缺資料","桃園區","商業區",True,1000)
    assert score(d)["grade"]=="資料不足，待查證"
    e=Candidate("已改建","桃園區","商業區",True,1000,10,.9,20,10,3,True)
    assert not score(e)["eligible"]
    print("PASS: zoning exclusion, missing-data gating, scoring, redeveloped exclusion")
