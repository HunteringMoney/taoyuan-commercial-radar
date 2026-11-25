#!/usr/bin/env python3
"""Inspect the actual official municipal map service discovered in municipal JS."""
import json,datetime,os,urllib.request,urllib.parse
from pathlib import Path
BASE="https://urbandatasrv.tycg.gov.tw/server/rest/services/TY_UPGIS/TYMap_SDE/MapServer"
OUT=Path(os.getenv("RUNNER_TEMP","/tmp"))/"official-planning-layer-schema.json"
def get(url, params=None):
 if params:url+="?"+urllib.parse.urlencode(params)
 req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 Taoyuan GIS source audit"})
 with urllib.request.urlopen(req,timeout=26) as response:return json.load(response)
def main():
 result={"timestamp":datetime.datetime.now(datetime.timezone.utc).isoformat(),"base":BASE,"layers":[],"errors":[],"verified_commercial_geometry":False}
 try:
  root=get(BASE,{"f":"json"})
  result["root"]={"description":str(root.get("description",""))[:350],"copyrightText":root.get("copyrightText"),"capabilities":root.get("capabilities"),"currentVersion":root.get("currentVersion")}
  layers=root.get("layers",[])
  result["layers"]=[{"id":x.get("id"),"name":x.get("name")} for x in layers]
  interesting=[x for x in layers if any(k in x.get("name","") for k in ["土地使用","使用分區","都市計畫","行政區","計畫區","分區","街廓"])]
  result["interesting_count"]=len(interesting)
  for x in (interesting[:18]+[y for y in layers if y.get("id") in [0,22]])[:23]:
   lid=x.get("id")
   try:
    d=get(f"{BASE}/{lid}",{"f":"json"})
    out={"id":lid,"name":x.get("name"),"geometryType":d.get("geometryType"),"capabilities":d.get("capabilities"),"extent":d.get("extent"),
         "displayField":d.get("displayField"),"fields":[{"name":f.get("name"),"alias":f.get("alias")} for f in d.get("fields",[])],"copyright":d.get("copyrightText")}
    if "Query" in str(d.get("capabilities")) and d.get("type")!="Group Layer":
     try:
      q=get(f"{BASE}/{lid}/query",{"f":"json","where":"1=1","outFields":"*","returnGeometry":"false","resultRecordCount":3})
      out["samples"]=[f.get("attributes") for f in q.get("features",[])];out["error"]=q.get("error")
     except Exception as e:out["sample_query_error"]=str(e)[:200]
    result.setdefault("details",[]).append(out)
   except Exception as e:result["errors"].append({"layer":lid,"message":str(e)[:150]})
  result["status"]="metadata_obtained_not_yet_legally_verified"
 except Exception as e:
  result["status"]="unreachable";result["errors"].append({"service":str(e)[:250]})
 OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
 print("OFFICIAL_PLANNING_SCHEMA:",json.dumps(result,ensure_ascii=False)[:30000])
if __name__=="__main__":main()
