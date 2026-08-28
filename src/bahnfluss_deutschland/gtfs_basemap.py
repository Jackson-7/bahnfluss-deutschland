import json
from functools import lru_cache
from pathlib import Path

from matplotlib.collections import LineCollection
from matplotlib.colors import to_rgba
from matplotlib.path import Path as MatplotlibPath
from matplotlib.patches import PathPatch

from bahnfluss_deutschland.gtfs_theme import (
    MAP_FILL,
    MAP_FILL_ALPHA,
    MAP_OUTLINE,
    MAP_OUTLINE_ALPHA,
)


GERMANY_BOUNDARY_PATH = (
    Path(__file__).resolve().parent
    / "assets"
    / "germany_natural_earth_10m.geojson"
)


def _iter_geometry_polygons(geometry):
    if geometry["type"] == "Polygon":
        yield geometry["coordinates"]
    elif geometry["type"] == "MultiPolygon":
        yield from geometry["coordinates"]
    else:
        raise ValueError(f"Unsupported boundary geometry type: {geometry['type']}")


@lru_cache(maxsize=1)
def load_germany_boundary():
    if not GERMANY_BOUNDARY_PATH.exists():
        return []

    with GERMANY_BOUNDARY_PATH.open(encoding="utf-8") as file:
        geojson = json.load(file)

    polygons = []
    for feature in geojson["features"]:
        for polygon in _iter_geometry_polygons(feature["geometry"]):
            rings = [
                [(float(lon), float(lat)) for lon, lat in ring]
                for ring in polygon
                if len(ring) >= 4
            ]
            if rings:
                polygons.append(rings)
    return polygons


def _path_from_rings(rings, transform=lambda lon, lat: (lon, lat)):
    vertices = []
    codes = []
    for ring in rings:
        closed_ring = ring if ring[0] == ring[-1] else [*ring, ring[0]]
        for index, (lon, lat) in enumerate(closed_ring):
            vertices.append(transform(lon, lat))
            if index == 0:
                codes.append(MatplotlibPath.MOVETO)
            elif index == len(closed_ring) - 1:
                codes.append(MatplotlibPath.CLOSEPOLY)
            else:
                codes.append(MatplotlibPath.LINETO)
    return MatplotlibPath(vertices, codes)


def _ring_segments(rings, transform=lambda lon, lat: (lon, lat)):
    segments = []
    for ring in rings:
        closed_ring = ring if ring[0] == ring[-1] else [*ring, ring[0]]
        segments.extend(
            [
                [transform(*closed_ring[index]), transform(*closed_ring[index + 1])]
                for index in range(len(closed_ring) - 1)
            ]
        )
    return segments


def add_germany_map_background(
    ax, fill_alpha=MAP_FILL_ALPHA, outline_alpha=MAP_OUTLINE_ALPHA
):
    polygons = load_germany_boundary()
    if not polygons:
        return

    for rings in polygons:
        patch = PathPatch(
            _path_from_rings(rings),
            facecolor=MAP_FILL,
            edgecolor="none",
            alpha=fill_alpha,
            zorder=0,
        )
        ax.add_patch(patch)

        outline = LineCollection(
            _ring_segments(rings),
            colors=[to_rgba(MAP_OUTLINE, outline_alpha)],
            linewidths=0.55,
            capstyle="round",
            joinstyle="round",
            zorder=1,
        )
        ax.add_collection(outline)


def add_germany_watermark(ax, bounds=(0.72, 0.08, 0.22, 0.46)):
    polygons = load_germany_boundary()
    if not polygons:
        return

    points = [
        point
        for polygon in polygons
        for ring in polygon
        for point in ring
    ]
    min_lon = min(lon for lon, _lat in points)
    max_lon = max(lon for lon, _lat in points)
    min_lat = min(lat for _lon, lat in points)
    max_lat = max(lat for _lon, lat in points)
    left, bottom, width, height = bounds

    def normalise(lon, lat):
        return (
            left + ((lon - min_lon) / (max_lon - min_lon)) * width,
            bottom + ((lat - min_lat) / (max_lat - min_lat)) * height,
        )

    for rings in polygons:
        patch = PathPatch(
            _path_from_rings(rings, transform=normalise),
            transform=ax.transAxes,
            facecolor=MAP_FILL,
            edgecolor=MAP_OUTLINE,
            linewidth=0.65,
            alpha=0.12,
            zorder=0,
        )
        ax.add_patch(patch)
