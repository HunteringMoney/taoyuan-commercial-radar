import unittest

from shapely.geometry import box, mapping

from pilot_scout import build


def feature(geom, props):
    return {"type": "Feature", "geometry": mapping(geom), "properties": props}


def osm_way(identifier, geom):
    return {"type": "way", "id": identifier, "tags": {"building": "yes"},
            "geometry": [{"lon": x, "lat": y} for x, y in geom.exterior.coords]}


class PilotScoutTests(unittest.TestCase):
    def test_requires_both_red_screenshot_and_commercial_geometry(self):
        commercial = {"type": "FeatureCollection", "features": [feature(
            box(121.31, 24.99, 121.311, 24.991),
            {"LANDUSE": "商業區", "MUPLAN": "桃園市都市計畫"}), feature(
            box(121.311, 24.99, 121.312, 24.991),
            {"LANDUSE": "住宅區", "MUPLAN": "桃園市都市計畫"})]}
        parcel = {"type": "FeatureCollection", "features": [feature(
            box(121.3101, 24.9901, 121.3102, 24.9902), {"LANDNO8": "00550001"})]}
        red = {"type": "FeatureCollection", "features": [feature(
            box(121.3101, 24.9901, 121.312, 24.9909), {"verified_zoning_geometry": False})]}
        ways = [osm_way(i + 1, box(121.3102 + i * 0.00004, 24.9902,
                                   121.310225 + i * 0.00004, 24.990225)) for i in range(3)]
        ways.append(osm_way(4, box(121.3112, 24.9902, 121.31123, 24.99023)))  # residential
        ways.append(osm_way(5, box(121.3103, 24.99088, 121.31033, 24.99095)))  # mostly outside red
        _, report = build(commercial, parcel, {"elements": ways}, red)
        self.assertEqual(report["candidate_count"], 1)
        lead = report["targets"][0]
        self.assertEqual(lead["source_building_ids"], [1, 2, 3])
        self.assertFalse(lead["legal_zone_verified"])
        self.assertIsNone(lead["parcel_no"])
        self.assertIsNone(lead["building_age"])


if __name__ == "__main__":
    unittest.main()
