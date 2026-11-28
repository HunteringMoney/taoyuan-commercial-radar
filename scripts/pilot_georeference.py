#!/usr/bin/env python3
"""Turn a red zoning screenshot into a DRAFT geographic search mask.

Control points must be independently located on an authoritative map. A parcel
label alone is not a control point. Output is never a legal zoning boundary.
"""
import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
from shapely.geometry import Polygon, mapping


def fit_affine(points):
    if len(points) < 4:
        raise ValueError("At least four independently located control points are required")
    pixels = np.array([[p["pixel_x"], p["pixel_y"], 1] for p in points], dtype=float)
    earth = np.array([[p["longitude"], p["latitude"]] for p in points], dtype=float)
    if np.linalg.matrix_rank(pixels) != 3:
        raise ValueError("Control points are collinear")
    coefficients = np.linalg.lstsq(pixels, earth, rcond=None)[0]
    # Leave-one-out error prevents a three-point exact fit from posing as accuracy.
    errors = []
    for i in range(len(points)):
        subset = np.delete(pixels, i, 0)
        target = np.delete(earth, i, 0)
        if np.linalg.matrix_rank(subset) != 3:
            raise ValueError("Control points are poorly distributed")
        predicted = pixels[i] @ np.linalg.lstsq(subset, target, rcond=None)[0]
        dx = (predicted[0] - earth[i, 0]) * 101000
        dy = (predicted[1] - earth[i, 1]) * 111000
        errors.append(float(np.hypot(dx, dy)))
    return coefficients, errors


def extract_red(image, min_area_px=40):
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    # Restrict to saturated red so yellow residential zones and orange blocks
    # do not enter the trial mask. White roads split separate blocks.
    low = cv2.inRange(hsv, (0, 150, 80), (10, 255, 255))
    high = cv2.inRange(hsv, (170, 150, 80), (179, 255, 255))
    mask = cv2.bitwise_or(low, high)
    contours, hierarchy = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    polygons = []
    if hierarchy is None:
        return polygons, int(cv2.countNonZero(mask))
    for i, contour in enumerate(contours):
        if hierarchy[0][i][3] != -1:
            continue
        if cv2.contourArea(contour) < min_area_px:
            continue
        approximated = cv2.approxPolyDP(contour, 1.2, True)[:, 0, :]
        if len(approximated) < 3:
            continue
        holes = []
        child = hierarchy[0][i][2]
        while child != -1:
            ring = cv2.approxPolyDP(contours[child], 1.2, True)[:, 0, :]
            if len(ring) >= 3 and cv2.contourArea(contours[child]) >= min_area_px:
                holes.append(ring)
            child = hierarchy[0][child][0]
        polygon = Polygon(approximated, holes)
        if polygon.is_valid and polygon.area > 0:
            polygons.append(polygon)
    return polygons, int(cv2.countNonZero(mask))


def convert(image_path, control_path, output_path, report_path, max_error_m=30):
    source = Path(image_path)
    image = cv2.imread(str(source))
    if image is None:
        raise ValueError("Image cannot be read")
    controls = json.loads(Path(control_path).read_text(encoding="utf-8"))
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if controls.get("image_sha256") and controls["image_sha256"] != digest:
        raise ValueError("Control-point file belongs to a different image")
    if controls.get("image_pixels") and controls["image_pixels"] != [image.shape[1], image.shape[0]]:
        raise ValueError("Control-point image dimensions mismatch")
    points = controls.get("control_points", [])
    for point in points:
        if not point.get("source_url") or not point.get("feature_description"):
            raise ValueError("Each control point needs a source URL and feature description")
        if not (0 <= point["pixel_x"] < image.shape[1] and 0 <= point["pixel_y"] < image.shape[0]):
            raise ValueError("Control point outside image")
    coefficients, errors = fit_affine(points)
    if max(errors) > max_error_m:
        raise ValueError("Control-point leave-one-out error exceeds limit: %.1f m" % max(errors))
    pixel_polygons, count = extract_red(image)
    if not pixel_polygons:
        raise ValueError("No red regions detected")
    def project_ring(ring):
        arr = np.array([[x, y, 1] for x, y in ring.coords])
        return (arr @ coefficients).tolist()
    features = []
    for i, polygon in enumerate(pixel_polygons, 1):
        transformed = Polygon(project_ring(polygon.exterior),
                              [project_ring(ring) for ring in polygon.interiors])
        if not transformed.is_valid or transformed.area <= 0:
            raise ValueError("Transformed polygon invalid")
        features.append({"type": "Feature", "properties": {
            "id": "red-%03d" % i, "source": "user_screenshot",
            "zoning_status": "pending_official_verification",
            "verified_zoning_geometry": False,
            "not_legal_boundary": True}, "geometry": mapping(transformed)})
    report = {"status": "draft_only_pending_official_zoning_and_cadastre",
              "image_sha256": digest,
              "image_width": image.shape[1], "image_height": image.shape[0],
              "control_point_count": len(points), "leave_one_out_errors_m": [round(x, 2) for x in errors],
              "max_leave_one_out_error_m": round(max(errors), 2),
              "red_pixel_count": count, "draft_polygon_count": len(features),
              "caveat": "Screenshot colors are trial search hints, not confirmed statutory zoning."}
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False, indent=2), encoding="utf-8")
    Path(report_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--control-points", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--max-error-m", type=float, default=30)
    args = parser.parse_args()
    print(json.dumps(convert(args.image, args.control_points, args.output, args.report, args.max_error_m), ensure_ascii=False))


if __name__ == "__main__":
    main()
