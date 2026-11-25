"""Only synthetic polygons. Tests are NOT verified real-world Taoyuan zoning."""
import unittest
from shapely.geometry import box, mapping
from validate_official_commercial_boundary import accept

META={"plan_name":"SYNTHETIC TEST NOT REAL","legal_announcement_date":"2026-01-01",
      "source_url":"https://urplanning.tycg.gov.tw/gisMap/Map.aspx",
      "source_agency":"桃園市政府都市發展局","boundary_source_url":"https://data.gov.tw",
      "boundary_version":"synthetic","zoning_version":"synthetic",
      "license_reviewed":True,"operator_approved":True,"crs":"EPSG:4326"}
def feat(geom, props):
    return {"type":"Feature","properties":props,"geometry":mapping(geom)}
def fc(*features):return {"type":"FeatureCollection","features":list(features)}
class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.district=fc(feat(box(0,0,10,10),{"COUNTY":"桃園市","TOWN":"桃園區"}))
    def test_only_commercial_and_fully_inside(self):
        f=fc(feat(box(1,1,2,2),{"使用分區":"商業區"}),
             feat(box(3,3,4,4),{"使用分區":"住宅區"}),
             feat(box(9,9,11,11),{"使用分區":"第一種商業區"}),
             feat(box(12,12,13,13),{"使用分區":"商業區"}))
        result,report=accept(f,self.district,META)
        self.assertEqual(len(result["features"]),1)
        self.assertEqual(report["rejected"]["other_zone"],1)
        self.assertEqual(report["rejected"]["crosses_district"],1)
        self.assertEqual(report["rejected"]["other_district"],1)
    def test_no_approval_never_passes(self):
        with self.assertRaises(ValueError):
            accept(fc(feat(box(1,1,2,2),{"使用分區":"商業區"})),
                   self.district,{**META,"operator_approved":False})
    def test_unclear_zone_never_passes(self):
        r,_=accept(fc(feat(box(1,1,2,2),{"AA08":"A"})),self.district,META)
        self.assertEqual(r["features"],[])
if __name__=="__main__":
    unittest.main()
