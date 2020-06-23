import configparser
import os
import fiona
import rasterio

import numpy as np

from rasterio import MemoryFile
from rasterio.mask import mask
from rasterio.merge import merge
from shapely.geometry import box, Polygon

from src.tile import Tile
from src.utils.helpers import Stages


NO_DATA = -9999


class Raster:
    def __init__(self, raster_name, filepath, stage):
        self._raster_name = raster_name
        self._raster = None
        self._stage = stage

        self.filepath = filepath

        directory = os.path.dirname(os.path.realpath(__file__))

        config = configparser.ConfigParser()
        config.read(os.path.join(directory, "config.ini"))

        self._in_progress_path = config["folder_paths"]["processing"]
        self._finished_path = config["folder_paths"]["finished"]
        self._polygon_paths = config["folder_paths"]["flattening_polygons"]

        self._base_raster_cell_size = float(config["global"]["base_raster_cell_size"])

        polygon_paths = os.path.join(config["folder_paths"]["flattening_polygons"], 'homogenization')
        self._polygons = [os.path.join(polygon_paths, f) for f in os.listdir(polygon_paths) if ".shp" in f]

    def get_raster_name(self):
        return self._raster_name

    def get_stage(self):
        return self._stage

    def open(self):
        self._raster = rasterio.open(self.filepath)
        return self._raster

    def close(self):
        self._raster.close()

    def get_downsampled_save_location(self):
        if self._stage in Stages.INTERPOLATED_DTM:
            prefix = "M5_"
        else:
            prefix = "R5_"

        return os.path.join(
            self._finished_path,
            prefix + self._raster_name + ".TIF"
        )

    def clip(self, tile: Tile):
        """ Clips this raster according to the size of original geometry of the tile provided
        :param tile: Tile element corresponding with this raster
        :return: None
        """
        try:
            self.open()

        except Exception:
            return False

        clip_geom = tile.get_unbuffered_geometry()
        clip_height = clip_geom.bounds[3] - clip_geom.bounds[1]  # maxy - miny
        clip_width = clip_geom.bounds[2] - clip_geom.bounds[0]  # maxx - minx

        try:
            print(self._raster_name, clip_geom)
            out_image, out_transform = mask(dataset=self._raster, shapes=[clip_geom], crop=True)

            out_meta = self._raster.meta.copy()

            self.close()

            out_meta.update({
                "driver": "GTiff",
                "height": clip_height / self._base_raster_cell_size,
                "width": clip_width / self._base_raster_cell_size,
                "transform": out_transform,
            })

            with rasterio.Env():
                with rasterio.open(self.filepath, "w", **out_meta) as dest:
                    dest.write(out_image)

        except Exception as e:
            print(e)
            return False

    def homogenize_patchwork(self):
        """ Uses a complete water polygon for all water bodies to fix the patched water bodies from the subtiles.
        Each subtile will interpolate its own value for the water, creating distinct lines, this function will take
        the mean of these different patches and apply that value to an overlapping polygon which replaces all the
        patched cells.

        :return: None
        """
        raster = rasterio.open(self.filepath)
        bbox = raster.bounds

        print(bbox)

        bbox = box(minx=bbox[0], miny=bbox[1], maxx=bbox[2], maxy=bbox[3])

        print(bbox)

        poly_list = []

        for shapefile in self._polygons:
            # find out which shapes intersect the bbox
            with fiona.open(shapefile) as src_water:

                for feature in src_water:

                    coord = feature['geometry']['coordinates']

                    if len(coord) > 1:
                        poly = Polygon(coord[0], coord[1:])

                    else:
                        poly = Polygon(coord[0])

                    # check if intersects with this tile (so if we need to do something)
                    if poly.intersects(bbox):
                        poly_list.append(feature["geometry"])

        print(len(poly_list))

        for polygon in poly_list:
            original = rasterio.open(self.filepath)

            try:
                # get the polygon as mask
                out_image, out_transform = mask(original, [polygon], crop=True)
                out_meta = original.meta.copy()

                out_meta.update(
                    {"driver": "GTiff",
                     "height": out_image.shape[1],
                     "width": out_image.shape[2],
                     "transform": out_transform}
                )

                # calculate the mean and change all the values, which are not nodata into the mean
                mean = np.mean(out_image[out_image != NO_DATA])

                print(mean)

                out_image[out_image != NO_DATA] = mean

                with MemoryFile() as memfile:
                    with memfile.open(**out_meta) as dataset:
                        dataset.write(out_image)

                    merge_image, merge_transform = merge([memfile.open(), original])
                    memfile.close()

                out_meta.update(
                    {"driver": "GTiff",
                     "height": merge_image.shape[1],
                     "width": merge_image.shape[2],
                     "transform": merge_transform}
                )

                original.close()

                with rasterio.open(self.filepath, "w", **out_meta) as dest:
                    dest.write(merge_image)

            except:
                pass
