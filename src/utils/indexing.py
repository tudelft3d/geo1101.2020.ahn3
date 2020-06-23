from shapely.geometry import *

from src.tile import Tile
from src.utils.helpers import get_ahn_index


def get_tile_connectivity():
    """ Uses data from AHN3 to transform all tiles into polygons, then doing intersection tests to determine if tiles
    are in some way connected (done by checking if exterior of 2 polygons intersects). If it intersects, then a few
    more tests are done te determine on which side the intersection is. When it is done, it assigns the neighboring
    tile in the correct place in the Tile class.

    Note: Possibly there is a more efficient way to do intersection tests and determining where a tile is in respect
    to another tile.

    :return: Dictionary containing tile id as key and Tile class as value
    """
    print("Getting AHN3 tile connectivity before starting...")
    data = get_ahn_index()

    if data is None:
        raise Exception("Could not retrieve tile data from AHN3 server")

    tiles = {}

    for tile in data:
        polygon = Polygon(tile['geometry']['coordinates'][0][0])
        tiles[tile['properties']['bladnr'].upper()] = polygon

    output_tiles = {}

    for tile_name_1 in tiles.keys():
        tile_poly_1 = tiles[tile_name_1]
        output_tiles[tile_name_1] = Tile(tile_name=tile_name_1, geometry=tile_poly_1)

        for tile_name_2 in tiles.keys():

            if tile_name_1 != tile_name_2:  # Don't check against same tile
                tile_poly_2 = tiles[tile_name_2]

                if tile_name_2 not in output_tiles.keys():
                    output_tiles[tile_name_2] = Tile(tile_name=tile_name_2, geometry=tile_poly_2)

                if tile_poly_1.touches(tile_poly_2):  # Are neighbors
                    intersection = tile_poly_1.exterior.intersection(tile_poly_2.exterior)

                    # Some polygons have non-straight edges (MultiLineString), simplify them
                    if intersection.geom_type == "MultiLineString":
                        # Round any points that may cause floating point issues
                        points = [round(coord) for coord in list(intersection.bounds)]
                        intersection = LineString([points[:2], points[2:]])

                    if intersection.geom_type == "Point":  # Is a single point of intersection (corner)
                        if intersection.x < tile_poly_1.centroid.x:  # Intersection is left of tile
                            if intersection.y < tile_poly_1.centroid.y:  # Intersection is below tile
                                output_tiles[tile_name_1]._bottom_left = output_tiles[tile_name_2]
                            else:
                                output_tiles[tile_name_1]._top_left = output_tiles[tile_name_2]
                        else:
                            if intersection.y < tile_poly_1.centroid.y:  # Intersection is above tile
                                output_tiles[tile_name_1]._bottom_right = output_tiles[tile_name_2]
                            else:
                                output_tiles[tile_name_1]._top_right = output_tiles[tile_name_2]

                    elif intersection.geom_type == "LineString":  # Is a line of intersection (sides)
                        if intersection.coords[0][0] == intersection.coords[1][0]:  # X axis is unchanged
                            if intersection.coords[0][0] < tile_poly_1.centroid.x:  # Intersection is left of tile
                                output_tiles[tile_name_1]._left = output_tiles[tile_name_2]
                            else:
                                output_tiles[tile_name_1]._right = output_tiles[tile_name_2]
                        else:
                            if intersection.coords[0][1] < tile_poly_1.centroid.y:  # Intersection is below tile
                                output_tiles[tile_name_1]._bottom = output_tiles[tile_name_2]
                            else:
                                output_tiles[tile_name_1]._top = output_tiles[tile_name_2]

    return output_tiles
