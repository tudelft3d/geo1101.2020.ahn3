import configparser
import multiprocessing
import os
import rasterio

import numpy as np

from shapely.geometry import Point, MultiPoint
from rasterio.features import rasterize

from src.utils.helpers import vector_prepare, wfs_prepare, Stages

NO_DATA = -9999
MIN_N = 0


class Flatten:
    def __init__(self):
        """ Initializes all variables needed for the flattening functions
        """
        directory = os.path.dirname(os.path.realpath(__file__))

        config = configparser.ConfigParser()
        config.read(os.path.join(directory, "..", "config.ini"))

        self._raster_cell_size = float(config["global"]["base_raster_cell_size"])

        self._polygon_paths = config["folder_paths"]["flattening_polygons"]
        self._wfs_url = ['http://3dbag.bk.tudelft.nl/data/wfs', 'BAG3D:pand3d']

        self._polygons = [os.path.join(self._polygon_paths, f) for f in os.listdir(self._polygon_paths) if ".shp" in f]

    def water(self, origin, res, raster, tin, extents, stage):
        """ Function that flattens the water bodies that are present within the specified raster. Uses all local
        polygons in shapefile format that are available in the specified folder in the config, theoretically not limited
        to water. Retrieves the polygons within the bounding box of the raster to interpolate the median value for this
        polygon. Then overlays these values in the correct position in the raster to create flattened areas on the
        raster.

        :param origin: List containing the coordinates of the top left corner of the raster
        :param res: List containing the x and y resolution of the raster
        :param raster: Numpy array containing the content of the raster (x, y, z)
        :param tin: startin.DT() object containing all relevant LAS points for interpolating values of polygons
        :param extents: List containing the extents of the raster as [[minx, maxx], [miny, maxy]]
        :return: Numpy array containing raster with flattened areas where polygons were found
        """
        print('\n{0}: Starting to flatten water bodies'.format(
            multiprocessing.current_process().name,
        ))

        x0 = extents[0][0]
        x1 = extents[0][1]
        y0 = extents[1][0]
        y1 = extents[1][1]

        bbox = [[x0, x1], [y0, y1]]

        input_vectors = []

        for polygon in self._polygons:
            vec = vector_prepare(bbox=bbox, filepath=polygon)
            if len(vec) != 0:
                input_vectors.append(vec)

        if stage == Stages.INTERPOLATED_DTM:  # Only flatten buildings if it's DTM
            try:
                vec = wfs_prepare(bbox=bbox, url=self._wfs_url[0], layer=self._wfs_url[1])

                if len(vec) != 0:
                    input_vectors.append(vec)

            except:  # WFS server might be down
                pass

        if len(input_vectors) > 0 and tin is not None:
            xs = np.linspace(x0, x1, res[0])
            ys = np.linspace(y0, y1, res[1])
            xg, yg = np.meshgrid(xs, ys)

            cell_centers = np.vstack((xg.ravel(), yg.ravel(), raster.ravel())).transpose()

            data = cell_centers[cell_centers[:, 2] != NO_DATA]
            data_hull = MultiPoint(data).convex_hull

            shapes = []

            for polygons in input_vectors:
                for polygon in polygons:

                    els = []

                    for vertex in polygon.exterior.coords:

                        if Point(vertex).within(data_hull):
                            try:
                                els += [tin.interpolate_laplace(vertex[0], vertex[1])]

                            except OSError:  # Apparently we can sometimes still be outside CH
                                pass

                    for interior in polygon.interiors:
                        for vertex in interior.coords:

                            if Point(vertex).within(data_hull):
                                try:
                                    els += [tin.interpolate_laplace(vertex[0], vertex[1])]

                                except OSError:  # Apparently we can sometimes still be outside CH
                                    pass

                    if len(els) > 0:
                        shapes.append((polygon, np.median(els)))

            if len(shapes) > 0:
                transform = rasterio.transform.from_origin(
                    west=origin[0],
                    north=origin[1],
                    xsize=self._raster_cell_size,
                    ysize=self._raster_cell_size
                )

                raster_polygons = rasterize(shapes=shapes, out_shape=raster.shape, fill=NO_DATA, transform=transform)

                for yi in range(res[1]):
                    for xi in range(res[0]):
                        if raster_polygons[yi, xi] != NO_DATA:
                            raster[yi, xi] = raster_polygons[yi, xi]

        return raster

    @staticmethod
    def patch(res, raster):
        """ Function that patches in any holes that may have unwillingly occurred in the process. Checks if a raster
        value is NO_DATA, then uses the median of the 8 surrounding cells to give the missing cell a value. Only uses
        value of surrounding cell if that is not NO_DATA.

        :param res: List representing the resolution of the raster [x-res, y-res]
        :param raster: Numpy array holding the raster value [x, y, z]
        :return: Raster with all NO_DATA holes patched
        """
        mp = [[-1, -1], [-1, 0], [-1, 1], [0, -1], [0, 1], [1, -1], [1, 0], [1, 1]]

        for yi in range(res[1]):
            for xi in range(res[0]):

                if raster[yi, xi] == NO_DATA:
                    vals = []

                    for m in range(8):
                        xw, yw = xi + mp[m][0], yi + mp[m][1]

                        if 0 <= xw < res[0] and 0 <= yw < res[1]:
                            val = raster[yw, xw]

                            if val != NO_DATA:
                                vals += [val]

                    if len(vals) > MIN_N:
                        raster[yi, xi] = np.median(vals)

        return raster
