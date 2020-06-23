import configparser
import os
import rasterio

from rasterio.merge import merge

from src.tile import Tile
from src.utils.helpers import create_path_if_not_exists, Stages

PRECISION = 5
NO_DATA = -9999


class Merging:
    def __init__(self, tile: Tile, input_rasters: list):
        self._parent_tile = tile
        self._raster_list = input_rasters

        self._out_image = None
        self._out_meta = None
        self._out_transform = None

        directory = os.path.dirname(os.path.realpath(__file__))

        config = configparser.ConfigParser()
        config.read(os.path.join(directory, "..", "config.ini"))

        self._finished_path = config["folder_paths"]["finished"]

    def _get_save_location(self, stage):
        """ Uses the stage this raster is at (dsm or dtm) to apply the correct prefix for the output file

        :param stage: String representing stage (dsm or dtm)
        :return: String with full filepath to output file
        """
        path = os.path.join(
            self._finished_path
        )

        create_path_if_not_exists(path)

        if stage in Stages.INTERPOLATED_DTM:
            prefix = "M_"
        else:
            prefix = "R_"

        return os.path.join(
            path,
            prefix + self._parent_tile.get_tile_name() + ".TIF"
        )

    def save(self, stage):
        """ Saves the raster to location specified by _get_save_location function depending on what stage this raster is

        :param stage:
        :return:
        """
        save_name = self._get_save_location(stage)

        with rasterio.Env():
            with rasterio.open(save_name, "w", **self._out_meta) as dest:
                dest.write(self._out_image)

        return self._parent_tile.get_tile_name(), save_name

    def merge_rasters(self):
        """ Function that executes the merging of rasters using rasterio's merge function. Creates a single large raster
        based on all the small input rasters. Uses the geometry of the tile to determine where the bounds are to ensure
        raster is of correct size. Saves it to the location specified in the config.

        :return: None
        """
        input_rasters = []
        for raster in self._raster_list:
            input_rasters.append(raster.open())  # Load rasters into memory

        self._out_image, self._out_transform = merge(
            datasets=input_rasters,
            bounds=self._parent_tile.get_geometry().bounds,
            precision=PRECISION,
            nodata=NO_DATA,
        )

        self._out_meta = input_rasters[0].meta.copy()  # Copy any element for meta (CRS mostly)

        print("image shape:", self._out_image.shape)
        print("tile geom", self._parent_tile.get_geometry().bounds)

        self._out_meta.update(  # Set size of raster to mosaic size instead of size of single block
            {
                "driver": "GTiff",
                "height": self._out_image.shape[1],
                "width": self._out_image.shape[2],
                "transform": self._out_transform,
            }
        )

        for raster in self._raster_list:
            raster.close()  # Clear rasters from memory

