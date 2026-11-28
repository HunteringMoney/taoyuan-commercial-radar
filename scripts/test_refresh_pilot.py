import unittest

from shapely.geometry import box

from refresh_pilot import crosscheck_building_points


class PublicMapCrosscheckTests(unittest.TestCase):
    def setUp(self):
        footprint = box(121.3126, 24.9961, 121.3127, 24.9962)
        self.osm = {"elements": [{"type": "way", "id": 123, "geometry": [
            {"lon": x, "lat": y} for x, y in footprint.exterior.coords]}]}
        self.candidates = {"targets": [{"source_building_ids": [123]}]}

    def test_each_selected_building_requires_commercial_point_lookup(self):
        calls = []

        def query(_opener, _token, key, **fields):
            calls.append(key)
            if key == "GetSectLandByPoint":
                self.assertIn("x", fields)
                return [{"section": "0004", "parno": "0014-0002"}], "point-hash"
            return [{"zone_name": "商業區"}], "zone-hash"

        result = crosscheck_building_points(self.candidates, self.osm, object(), "test", query)
        self.assertEqual(calls, ["GetSectLandByPoint", "GetUsezoneBySectLand"])
        self.assertEqual(result["checked_building_count"], 1)
        self.assertFalse(result["legal_verification"])
        self.assertNotIn("section", str(result))
        self.assertNotIn("0014", str(result))

    def test_residential_or_mixed_result_stops_refresh(self):
        def query(_opener, _token, key, **_fields):
            if key == "GetSectLandByPoint":
                return [{"section": "0004", "parno": "0014-0002"}], "point-hash"
            return [{"zone_name": "商業區"}, {"zone_name": "住宅區"}], "zone-hash"

        with self.assertRaisesRegex(ValueError, "not wholly commercial"):
            crosscheck_building_points(self.candidates, self.osm, object(), "test", query)


if __name__ == "__main__":
    unittest.main()
