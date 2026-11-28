"""Synthetic-only geometry tests; no real-world zoning claims."""
import unittest
from shapely.geometry import box,mapping
from candidate_discovery import discover

def feat(geom,verified=True,zone="商業區"):
    return {"type":"Feature","geometry":mapping(geom),
            "properties":{"verified_zoning_geometry":verified,"使用分區":zone}}

class CandidateDiscoveryTests(unittest.TestCase):
    def setUp(self):
        # Tiny areas near Taoyuan; 0.00001 deg ~= 1 metre
        self.zones=[feat(box(121.30,24.99,121.31,25.00))]
        self.buildings=[feat(box(121.301+i*0.00004,24.991,121.301+i*0.00004+0.00002,24.99102)) for i in range(4)]
    def test_cluster(self):
        leads=discover(self.zones,self.buildings)
        self.assertEqual(len(leads),1)
        self.assertEqual(leads[0]["building_footprint_count"],4)
        self.assertEqual(leads[0]["status"],"screening_only_field_review_required")
    def test_omit_crossing_boundary(self):
        buildings=self.buildings+[feat(box(121.309999,24.999,121.3101,24.9991))]
        self.assertEqual(discover(self.zones,buildings)[0]["building_footprint_count"],4)
    def test_no_unverified_source(self):
        with self.assertRaises(ValueError):
            discover([feat(box(121.30,24.99,121.31,25),False)],self.buildings)
    def test_reject_residential(self):
        with self.assertRaises(ValueError):
            discover([feat(box(121.30,24.99,121.31,25),True,"住宅區")],self.buildings)
    def test_empty_is_not_successful_find(self):
        self.assertEqual(discover(self.zones,[]),[])
if __name__=="__main__":unittest.main()
