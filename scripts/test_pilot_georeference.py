import json
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from pilot_georeference import convert, extract_red, fit_affine


class GeoreferenceTests(unittest.TestCase):
    def test_four_spread_control_points_and_geojson(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = np.full((100, 120, 3), 255, dtype=np.uint8)
            cv2.rectangle(image, (15, 15), (55, 55), (0, 0, 220), -1)
            cv2.rectangle(image, (70, 15), (100, 55), (0, 255, 255), -1)
            image_file = root / "map.png"
            cv2.imwrite(str(image_file), image)
            points = []
            for x, y in [(0, 0), (119, 0), (0, 99), (119, 99), (60, 50)]:
                points.append({"pixel_x": x, "pixel_y": y,
                               "longitude": 121.3 + x * 0.00001,
                               "latitude": 25 - y * 0.00001,
                               "source_url": "https://example.test/control",
                               "feature_description": "synthetic control"})
            control_file = root / "controls.json"
            control_file.write_text(json.dumps({"control_points": points}))
            output = root / "scope.geojson"
            report = convert(image_file, control_file, output, root / "report.json")
            scope = json.loads(output.read_text())
            self.assertLess(report["max_leave_one_out_error_m"], 0.01)
            self.assertEqual(len(scope["features"]), 1)
            self.assertFalse(scope["features"][0]["properties"]["verified_zoning_geometry"])
            self.assertTrue(121.3 < scope["features"][0]["geometry"]["coordinates"][0][0][0] < 121.301)

    def test_three_points_cannot_claim_zero_error(self):
        with self.assertRaises(ValueError):
            fit_affine([{"pixel_x": 0, "pixel_y": 0, "longitude": 121, "latitude": 25}] * 3)

    def test_residential_yellow_is_excluded(self):
        image = np.full((60, 120, 3), 255, dtype=np.uint8)
        cv2.rectangle(image, (10, 10), (50, 50), (0, 0, 220), -1)
        cv2.rectangle(image, (60, 10), (100, 50), (0, 255, 255), -1)
        polygons, _ = extract_red(image)
        self.assertEqual(len(polygons), 1)

    def test_green_island_stays_outside_red_polygon(self):
        image = np.full((80, 80, 3), 255, dtype=np.uint8)
        cv2.rectangle(image, (5, 5), (74, 74), (0, 0, 220), -1)
        cv2.rectangle(image, (25, 25), (55, 55), (0, 255, 0), -1)
        polygons, _ = extract_red(image)
        self.assertEqual(len(polygons), 1)
        self.assertEqual(len(polygons[0].interiors), 1)


if __name__ == "__main__":
    unittest.main()
