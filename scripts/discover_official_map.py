#!/usr/bin/env python3
"""Inspect official TY urban planning GIS HTML and referenced frontend assets.

Discovery only: no zoning publication or target creation. Checks for programmatic
zoning feature endpoints used by official map, recording sources for manual review.
"""
import datetime,json,os,re,urllib.parse,urllib.request
from pathlib import Path
from html.parser import HTMLParser
BASE="https://urplanning.tycg.gov.tw"
PAGE=BASE+"/gisMap/Map.aspx"
OUT=Path(os.getenv("RUNNER_TEMP","/tmp"))/"urban-map-endpoints.json"
class Links(HTMLParser):
 def __init__(self):super().__init__();self.scripts=[]
 def handle_starttag(self,tag,attrs):
  d=dict(attrs)
  if tag=="script" and "src" in d:self.scripts.append(d["src"])
def read(url):
 req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 land-use data provenance research"})
 with urllib.request.urlopen(req,timeout=18) as r:
  content=r.read(800000)
 return content.decode("utf-8","replace")
def main():
 result={"checked":datetime.datetime.now(datetime.timezone.utc).isoformat(),"page":PAGE,"script_urls":[],"hints":[],"errors":[],"official_polygon_verified":False}
 try:
  html=read(PAGE); parser=Links();parser.feed(html)
  scripts=[urllib.parse.urljoin(PAGE,s) for s in parser.scripts]
  result["script_urls"]=scripts[:80]
  terms=re.compile(r'(https?://[^\s"\x27<>]{5,230}|[\w/.-]{4,140}(?:MapServer|FeatureServer|GetFeature|WMS|GetMap|geojson|serviceurl|GISMap|ArcGIS|usezone)[\w/.?=&-]{0,160})',re.I)
  texts=[("page",html)]
  for s in scripts:
   if not urllib.parse.urlparse(s).hostname.endswith("tycg.gov.tw"):continue
   if len(texts)>=18:break
   try:texts.append((s,read(s)))
   except Exception as e:result["errors"].append({"url":s,"error":str(e)[:100]})
  for name,body in texts:
   hits=list(dict.fromkeys(x.group(0) for x in terms.finditer(body)))
   if hits:result["hints"].append({"source":name,"hits":hits[:35]})
  print("OFFICIAL_MAP_DISCOVERY:",json.dumps(result,ensure_ascii=False)[:18000])
 except Exception as e:result["errors"].append({"page":str(e)[:300]});print("OFFICIAL_MAP_DISCOVERY_ERROR:",str(e)[:300])
 OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
if __name__=="__main__":main()
