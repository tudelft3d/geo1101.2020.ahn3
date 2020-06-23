import configparser
import multiprocessing
import os
import time
import traceback

import rasterio
import startin

import numpy as np

from scipy.spatial import cKDTree

from src.ground_filtering.ground_filtering import GroundFiltering
from src.interpolation.flatten import Flatten
from src.raster import Raster
from src.tile import Tile
from src.utils.helpers import Stages

NO_DATA = -9999


class Interpolation:
    def __init__(self, input_tile: Tile, result_type: str):
        self._tile = input_tile

        directory = os.path.dirname(os.path.realpath(__file__))

        config = configparser.ConfigParser()
        config.read(os.path.join(directory, "..", "config.ini"))

        self._to_overwrite = True if config["global"]["overwrite_existing_files"] == "true" else False

        self._raster_cell_size = float(config["global"]["base_raster_cell_size"])

        self._interpolation_variables = config["interpolation_dsm"] if result_type == "dsm" else config["interpolation_dtm"]
        self._stage = Stages.INTERPOLATED_DSM if result_type == "dsm" else Stages.INTERPOLATED_DTM

        tile_bounds = self._tile.get_unbuffered_geometry().bounds
        tile_bounds = [int(bound) for bound in tile_bounds]
        
        self._raster = None
        self._las_data = None

        self._tin = startin.DT()

        # [[minx, maxx], [miny, maxy]]
        self._extents = [[tile_bounds[0], tile_bounds[2]], [tile_bounds[1], tile_bounds[3]]]

        # Use width/height / raster cell size for x/y resolution
        self._resolution = [int((tile_bounds[2] - tile_bounds[0]) // self._raster_cell_size),
                            int((tile_bounds[3] - tile_bounds[1]) // self._raster_cell_size)]

        # Origin = [minx, maxy] == topleft corner
        self._origin = [tile_bounds[0], tile_bounds[3]]

        self._y_range = reversed(np.arange(
            start=tile_bounds[1],
            stop=tile_bounds[1] + self._resolution[1] * self._raster_cell_size,
            step=self._raster_cell_size
        ))

        self._x_range = np.arange(
            start=tile_bounds[0],
            stop=tile_bounds[0] + self._resolution[0] * self._raster_cell_size,
            step=self._raster_cell_size
        )

        print('extents', self._extents)
        print('resolution', self._resolution)
        print('origin', self._origin)

    def interpolate(self):
        save_name = self._get_save_name()

        interpolation_success = False

        # Empty LAS is 229 bytes, can happen if there are 0 points in that subtile
        # TODO: More elegant solution
        if os.path.getsize(self._tile.filepath) < 1000:
            print("Size of input file is less than 1000 bytes, not interpolating")

        elif os.path.exists(save_name) and self._to_overwrite is True or not os.path.exists(save_name):

            try:
                self._do_pre_processing()

                if self._stage == Stages.INTERPOLATED_DTM:
                    interpolation_success = self._startin_laplace()

                else:
                    interpolation_success = self._quad_idw()

                self._do_post_processing()

                self._save_raster()

            except Exception as e:
                print('\n{0}: Ran into an error while interpolating: {1}'.format(
                    multiprocessing.current_process().name,
                    str(e)
                ))
                traceback.print_exc()

        elif os.path.exists(save_name):
            # File already exists so assuming interpolation was a success previously
            interpolation_success = True

        if interpolation_success is True:
            self._tile.related_raster = Raster(
                raster_name=self._tile.get_tile_name(),
                filepath=save_name,
                stage=self._stage
            )

        self._tile.interpolated = True

    def _get_save_name(self):
        return self._tile.get_save_path(
            stage=self._stage, subtile_id=self._tile.get_tile_name(), extension="TIF"
        )

    def _save_raster(self):
        transform = rasterio.transform.from_origin(
            west=self._origin[0],
            north=self._origin[1],
            xsize=self._raster_cell_size,
            ysize=self._raster_cell_size
        )

        self._raster = self._raster.astype(np.float32)

        with rasterio.Env():

            with rasterio.open(
                    self._get_save_name(),
                    "w",
                    driver='GTiff',
                    height=self._raster.shape[0],
                    width=self._raster.shape[1],
                    count=1,
                    dtype=str(self._raster.dtype),
                    crs='EPSG:28992',
                    transform=transform,
                    nodata=NO_DATA
            ) as dest:
                dest.write(self._raster, 1)

    def _do_pre_processing(self):
        print('\n{0}: Starting filtering of outliers'.format(
            multiprocessing.current_process().name,
        ))

        ground_filtering = GroundFiltering(input_tile=self._tile)

        self._las_data = ground_filtering.remove_outliers(self._stage)

        self._las_data = np.asarray(self._las_data[0].tolist())[:, :3]

        print('\n{0}: Finished outlier filtering'.format(
            multiprocessing.current_process().name,
        ))

        self._tin.insert(self._las_data)

    def _do_post_processing(self):
        print(self._raster)

        flatten = Flatten()

        self._raster = flatten.water(
            origin=self._origin,
            res=self._resolution,
            raster=self._raster,
            tin=self._tin,
            extents=self._extents,
            stage=self._stage
        )

        print(self._raster)

        self._raster = flatten.patch(res=self._resolution, raster=self._raster)

        print(self._raster)

    def _startin_laplace(self):
        """Takes the grid parameters and the ground points. Interpolates using Laplace method.
        """
        print('\n{0}: Starting Laplace'.format(
            multiprocessing.current_process().name,
        ))

        start_time = time.time()

        self._raster = np.zeros([self._resolution[1], self._resolution[0]])

        yi = 0

        for y in self._y_range:
            xi = 0

            for x in self._x_range:
                tri = self._tin.locate(x, y)

                if tri != [] and 0 not in tri:
                    try:
                        self._raster[yi, xi] = self._tin.interpolate_laplace(x, y)

                    except Exception as e:
                        print(e)

                else:
                    self._raster[yi, xi] = NO_DATA

                xi += 1
            yi += 1

        print('\n{0}: Finished Laplace in {1} seconds'.format(
            multiprocessing.current_process().name,
            time.time() - start_time
        ))

        return True

    def _quad_idw(self):
        start_rk = 1
        pwr = 2
        minp = 1
        incr_rk = 3
        tolerance = 2
        maxiter = 2

        print('\n{0}: Starting Quad IDW'.format(
            multiprocessing.current_process().name,
        ))

        start_time = time.time()

        ras = np.zeros([self._resolution[1], self._resolution[0]])
        tree = cKDTree(np.array([self._las_data[:, 0], self._las_data[:, 1]]).transpose())

        yi = 0

        for y in self._y_range:
            xi = 0

            for x in self._x_range:
                done = False
                i = 0
                rk = start_rk
                xyp = []

                while done is False:
                    ix = tree.query_ball_point([x, y], rk, tolerance)

                    if len(ix) >= 4 * minp:  # Need at least minp points per quadrant

                        xyp = self._las_data[ix]

                        qs = [
                            xyp[(xyp[:, 0] < x) & (xyp[:, 1] < y)],
                            xyp[(xyp[:, 0] > x) & (xyp[:, 1] < y)],
                            xyp[(xyp[:, 0] < x) & (xyp[:, 1] > y)],
                            xyp[(xyp[:, 0] > x) & (xyp[:, 1] > y)]
                        ]

                        if min(qs[0].size, qs[1].size, qs[2].size, qs[3].size) >= minp:
                            done = True

                    if i >= maxiter:
                        ras[yi, xi] = NO_DATA
                        break

                    rk += incr_rk
                    i += 1

                else:
                    a_sum = 0
                    b_sum = 0

                    for pt in xyp:
                        dst = np.sqrt((x - pt[0]) ** 2 + (y - pt[1]) ** 2)

                        if dst > 0:
                            u = pt[2]
                            w = 1 / dst ** pwr

                            a_sum += u * w
                            b_sum += w

                    if b_sum > 0:
                        ras[yi, xi] = a_sum / b_sum

                    else:
                        ras[yi, xi] = NO_DATA

                xi += 1
            yi += 1

        print('\n{0}: Finished Quad IDW in {1} seconds'.format(
            multiprocessing.current_process().name,
            time.time() - start_time
        ))

        self._raster = ras

        return True
