import configparser
import math
import multiprocessing
import os
import subprocess
import time

from shapely.geometry import box

from src.tile import Tile, TileTypes
from src.utils.helpers import Stages


class Subtiling:
    def __init__(self, tile: Tile, connectivity: dict):
        """ Helper class that orchestrates subdivision of a single tile into subtiles.

        :param tile: Tile object for the tile that is to be subdivided
        :param connectivity: Dictionary containing all Tile objects and their respective connectivity
        """
        self._parent_tile = tile
        self._connectivity = connectivity

        self._subtiles = []

        self._min_coord = []
        self._max_coord = []

        directory = os.path.dirname(os.path.realpath(__file__))

        config = configparser.ConfigParser()
        config.read(os.path.join(directory, "..", "config.ini"))

        self._num_rows = int(config["tile_parameters"]["subtile_row_count"])
        self._num_cols = int(config["tile_parameters"]["subtile_column_count"])
        self._buffer = int(config["tile_parameters"]["buffer_in_m"])
        self._to_overwrite = True if config["global"]["overwrite_existing_files"] == "true" else False

        self._base_raster_cell_size = float(config["global"]["base_raster_cell_size"])

    def set_tile_extents(self):
        """ The bounds of the tile geometry to retrieve the bounding box of the point cloud.
        Stores this information in the class variables _min_coord and _max_coord.

        :return: None
        """
        if self._parent_tile.get_tile_type() == TileTypes.SUBTILE:
            self._min_coord = self._parent_tile.get_unbuffered_geometry().bounds[:2]
            self._max_coord = self._parent_tile.get_unbuffered_geometry().bounds[2:]

        else:
            self._min_coord = self._parent_tile.get_geometry().bounds[:2]
            self._max_coord = self._parent_tile.get_geometry().bounds[2:]

    def subdivide_tile(self):
        """ Creates all subtiles and stores them in the class variable _subtiles.

        Creation is done by taking the difference between the extremes in x and y direction, then dividing this by the
        number of rows or columns to provide a cell width/height. Then for each cell the bounding box is created and
        stored.

        :return: None
        """
        min_x = self._min_coord[0]
        min_y = self._min_coord[1]

        # Round to highest nearby multiple of base to ensure complete raster cells fit inside the subtile
        base = self._base_raster_cell_size
        delta_x = int(base * math.ceil(float((self._max_coord[0] - self._min_coord[0]) / self._num_cols) / base))
        delta_y = int(base * math.ceil(float((self._max_coord[1] - self._min_coord[1]) / self._num_rows) / base))

        for col in range(self._num_cols):
            for row in range(self._num_rows):
                box_min_x = min_x + (delta_x * col)
                box_min_y = min_y + (delta_y * row)

                minx = box_min_x
                miny = box_min_y
                maxx = box_min_x + delta_x
                maxy = box_min_y + delta_y

                # Ensure size doesn't become larger than desired due to the math.ceil rounding used
                if maxx >= self._max_coord[0]:
                    # Cases occur where value is 84999.999 but should be 85000, hence round()
                    maxx = round(self._max_coord[0])

                if maxy >= self._max_coord[1]:
                    maxy = round(self._max_coord[1])

                self._subtiles.append(
                    {
                        "buffered": [minx - self._buffer, miny - self._buffer, maxx + self._buffer, maxy + self._buffer],
                        "unbuffered": [minx, miny, maxx, maxy]
                    }
                )

    def clip_tile_by_subtiles(self):
        """ Uses las2las from LAStools in a subprocess to clip the provided main tile (self._tile) into the determined
        subtile grid.

        Has checks to determine which other tiles should be included in the las2las command. This prevents the
        unnecessary merging of extra AHN3 tiles. Creates as many subprocesses as there are subtiles and waits for them
        all to complete before closing the function.

        :return: None
        """
        for subtile_id in range(1, len(self._subtiles) + 1):
            save_name = self._parent_tile.get_save_path(stage=Stages.SUBTILING, subtile_id=str(subtile_id), extension="LAS")

            subtile = self._subtiles[subtile_id - 1]

            tile_name = self._parent_tile.get_tile_name()
            subtile_name = tile_name + "_" + str(subtile_id)

            buffered_geometry = box(
                minx=subtile["buffered"][0],
                miny=subtile["buffered"][1],
                maxx=subtile["buffered"][2],
                maxy=subtile["buffered"][3]
            )

            unbuffered_geometry = box(
                minx=subtile["unbuffered"][0],
                miny=subtile["unbuffered"][1],
                maxx=subtile["unbuffered"][2],
                maxy=subtile["unbuffered"][3]
            )

            if os.path.exists(save_name) and self._to_overwrite or not os.path.exists(save_name):

                command = ['las2las', '-i', self._parent_tile.filepath]
                
                if subtile_id == 1:  # Bottom left
                    command.extend(self._connectivity[tile_name].get_bottom_left())

                elif subtile_id == self._num_rows:  # Top left
                    command.extend(self._connectivity[tile_name].get_top_left())

                elif subtile_id == self._num_rows * self._num_cols:  # Top right
                    command.extend(self._connectivity[tile_name].get_top_right())

                elif subtile_id == (self._num_rows * self._num_cols) - self._num_rows + 1:  # Bottom right
                    command.extend(self._connectivity[tile_name].get_bottom_right())

                elif self._num_rows > subtile_id > 1:  # Left side
                    command.extend(self._connectivity[tile_name].get_left())

                elif self._num_rows * self._num_cols > subtile_id > (self._num_rows * self._num_cols) - self._num_rows + 1:  # Right side
                    command.extend(self._connectivity[tile_name].get_right())

                elif subtile_id % self._num_rows == 0:  # Top
                    command.extend(self._connectivity[tile_name].get_top())

                elif subtile_id % self._num_rows == 1:  # Bottom (works as long as grid is relatively square
                    command.extend(self._connectivity[tile_name].get_bottom())

                command.extend(
                    ['-merged', '-o', save_name, '-keep_xy',
                     str(subtile["buffered"][0]),
                     str(subtile["buffered"][1]),
                     str(subtile["buffered"][2]),
                     str(subtile["buffered"][3])]
                )

                print(command)

                process = subprocess.Popen(
                    args=command,
                )

                start_time = time.time()
                process.communicate()
                process.wait()
                print('{0}: Split tile "{1}" in {2} seconds.'.format(
                    multiprocessing.current_process().name,
                    subtile_name,
                    str(round(time.time() - start_time, 2))
                ))

            self._subtiles[subtile_id - 1] = Tile(
                tile_name=subtile_name,
                geometry=buffered_geometry,
                tile_type=TileTypes.SUBTILE,
                unbuffered_geometry=unbuffered_geometry,
                parent_tile=self._parent_tile
            )

    def get_created_subtiles(self):
        """ Returns the list of subtile names, determined by appending _NUM to the original tile name, where NUM is the
        sequence id of the subtile.

        :return: List containing output names of subtiles
        """
        return self._subtiles
