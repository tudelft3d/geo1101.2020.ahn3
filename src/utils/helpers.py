import json
import multiprocessing
import fiona
import requests

from pathlib import Path
from shapely.geometry import Point, LineString, box, Polygon, shape
from shapely.ops import linemerge, unary_union, polygonize
from owslib.wfs import WebFeatureService

INDEX_URL = "https://geodata.nationaalgeoregister.nl/ahn3/wfs?SERVICE=WFS&VERSION=1.0.0&REQUEST=GetFeature&outputFormat=application/json&TYPENAME=ahn3:ahn3_bladindex&SRSNAME=EPSG:28992"


def create_path_if_not_exists(input_path):
    Path(input_path).mkdir(parents=True, exist_ok=True)


def get_ahn_index():
    """Download the newest AHN3 units/index file"""

    response = requests.get(INDEX_URL)
    if response.status_code == requests.codes.ok:
        data = response.json()

        return data['features']


def vector_prepare(bbox, filepath):
    """Takes a bounding box and a file path to a vector file.
    Reads the vector file, finds polygons that are within the
    bounding box or intersect it. Crops the intersecting geometries
    to the extents of the bounding box, and returns the contained and
    cropped geometries.

    :param bbox: List representing the bounding box used to retrieve polygons [[xmin, xmax], [ymin, ymax]]
    :param filepath: String representing path to where the polygon file can be found
    :return: List containing cutouts of the polygons which are inside the bounding box specified
    """
    a = Point(bbox[0][0], bbox[1][1])
    b = Point(bbox[0][1], bbox[1][1])
    c = Point(bbox[0][1], bbox[1][0])
    d = Point(bbox[0][0], bbox[1][0])

    bbox_lines = LineString([a, b, c, d, a])
    bbox_object = box(bbox[0][0], bbox[1][0], bbox[0][1], bbox[1][1])
    out = []

    for feature in fiona.open(filepath):

        merger = [bbox_lines]
        rings = feature['geometry']['coordinates']

        for ring_coords in rings:
            ring = Polygon(ring_coords)

            if ring.within(bbox_object):
                out.append(shape(feature['geometry']))

            elif ring.intersects(bbox_object):
                merger.append(ring.boundary)

        if len(merger) != 1:
            if len(rings) > 1:
                poly = Polygon(rings[0], rings[1:])

            else:
                poly = Polygon(rings[0])

            merged = linemerge(merger)
            borders = unary_union(merged)
            polygons = polygonize(borders)

            for p in polygons:
                try:
                    if p.within(bbox_object) and poly.contains(p.buffer(-1e-8)):

                        feature['geometry']['coordinates'] = [p.exterior.coords]
                        feature['properties']['Shape_Leng'] = p.length
                        feature['properties']['Shape_Area'] = p.area

                        out.append(shape(feature['geometry']))
                except Exception as e:
                    print('\n{0}: Ran TopologicalError: {1}'.format(
                        multiprocessing.current_process().name,
                        str(e)
                    ))

    return out


def wfs_prepare(bbox, url, layer):
    """Takes a bounding box and a WFS service URL.
    Requests features in the bounding box, finds polygons that are within
    the bounding box or intersect it. Crops the intersecting geometries
    to the extents of the bounding box, and returns the contained and
    cropped geometries.

    :param bbox: List representing the bounding box used to retrieve polygons [[xmin, xmax], [ymin, ymax]]
    :param url: String representing url to WFS service where polygons can be retrieved
    :param layer: String representing layer for which to request data from WFS service
    :return: List containing cutouts of the polygons which are inside the bounding box specified
    """
    a = Point(bbox[0][0], bbox[1][1])
    b = Point(bbox[0][1], bbox[1][1])
    c = Point(bbox[0][1], bbox[1][0])
    d = Point(bbox[0][0], bbox[1][0])

    bbox_lines = LineString([a,b,c,d,a])
    bbox_object = box(bbox[0][0], bbox[1][0], bbox[0][1], bbox[1][1])

    wfs = WebFeatureService(url=url, version='2.0.0')

    response = wfs.getfeature(
        typename=layer,
        bbox=(bbox[0][0], bbox[1][0], bbox[0][1], bbox[1][1]),
        outputFormat='json'
    )

    response_json = json.loads(response.read())

    for feature in response_json['features']:
        rings = feature['geometry']['coordinates']

        for ring_coords, i in zip(rings, range(len(rings))):
            ring = [vx[0:2] for vx in ring_coords]
            feature['geometry']['coordinates'][i] = ring

    out = []

    for feature in response_json['features']:
        merger = [bbox_lines]
        rings = feature['geometry']['coordinates']

        for ring_coords in rings:
            ring = Polygon(ring_coords)

            if ring.within(bbox_object):
                out.append(shape(feature['geometry']))

            elif ring.intersects(bbox_object):
                merger.append(ring.boundary)

        if len(merger) != 1:
            if len(rings) > 1:
                poly = Polygon(rings[0], rings[1:])

            else:
                poly = Polygon(rings[0])

            merged = linemerge(merger)
            borders = unary_union(merged)
            polygons = polygonize(borders)

            for p in polygons:
                try:
                    if p.within(bbox_object) and poly.contains(p.buffer(-1e-8)):
                        feature['geometry']['coordinates'] = [p.exterior.coords]
                        feature['properties']['Shape_Leng'] = p.length
                        feature['properties']['Shape_Area'] = p.area

                        out.append(shape(feature['geometry']))

                except Exception as e:
                    print('\n{0}: Ran TopologicalError: {1}'.format(
                        multiprocessing.current_process().name,
                        str(e)
                    ))

    return out


class Stages:
    SUBTILING = "subtiles"
    FILTERED = "filtered"
    INTERPOLATED_DSM = "interpolated_dsm"
    INTERPOLATED_DTM = "interpolated_dtm"
