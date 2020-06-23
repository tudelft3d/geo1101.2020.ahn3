import configparser
import os

from laspy.file import File
from shapely.geometry import Polygon

from src.utils.helpers import create_path_if_not_exists, Stages


class TileTypes:
    MAIN = "main"
    SUBTILE = "subtile"


class Tile:
    def __init__(
            self,
            tile_name: str,
            geometry: Polygon,
            tile_type: str = TileTypes.MAIN,
            unbuffered_geometry: Polygon = None,
            parent_tile: 'Tile' = None
    ):
        """ Helper class to keep relations between tiles in a central place.

        :param tile_name: str representing name of main tile, e.g. 37EN1 or 37EN1_1
        :param geometry: Polygon geometry of the tile
        :param tile_type:
        :param unbuffered_geometry:
        """
        self._tile_name = tile_name.upper()
        self._tile_type = tile_type
        self._geometry = geometry
        self._unbuffered_geometry = unbuffered_geometry
        self._parent_tile = parent_tile

        self.related_raster = None
        self.interpolated = False

        self._top_left = None
        self._top = None
        self._top_right = None
        self._right = None
        self._bottom_right = None
        self._bottom = None
        self._bottom_left = None
        self._left = None

        self._children_processed = 0

        directory = os.path.dirname(os.path.realpath(__file__))

        config = configparser.ConfigParser()
        config.read(os.path.join(directory, "config.ini"))

        self._base_path = config["folder_paths"]["ahn3_tiles"]
        self._processing_path = config["folder_paths"]["processing"]

        self._file = None

        self.filepath = None
        self._set_filepath()

    def get_parent_tile(self):
        return self._parent_tile

    def get_tile_type(self):
        return self._tile_type

    def get_geometry(self):
        return self._geometry

    def get_unbuffered_geometry(self):
        return self._unbuffered_geometry

    def get_tile_name(self):
        return self._tile_name

    def open(self):
        self._file = File(self.filepath, mode='r')
        return self._file

    def close(self):
        self._file.close()

    def _set_filepath(self):
        if self._tile_type == TileTypes.SUBTILE:
            tile_path = os.path.join(
                self._processing_path,
                self._tile_name.split("_")[0],
                Stages.SUBTILING
            )
            tile_name = self._tile_name.split("_")[-1]

        else:
            tile_path = self._base_path
            tile_name = self._tile_name

        # Provides full path for tile based on name
        tile_file = [f for f in os.listdir(tile_path) if tile_name == f.split(".")[0] or tile_name.lower() == f.split(".")[0]]

        if len(tile_file) > 0:  # Found a file that matches this tile name in the folder, so using that
            self.filepath = os.path.join(tile_path, tile_file[0])

        elif self._tile_type == TileTypes.MAIN:
            self.filepath = os.path.join(self._base_path, "C_" + tile_name + ".LAZ")
            # print("Could not find specified tile in the expected folder!", self._tile_name, tile_path)

        elif self._tile_type == TileTypes.SUBTILE:
            self.filepath = os.path.join(tile_path, tile_name + ".LAS")

        else:
            print("Something went wrong, couldn't find tile specified", tile_path, tile_name)

    def get_save_path(self, stage: str, subtile_id: str, extension: str):
        """ Returns full path for any processing stage based on the id provided

        Save to: base path \\ tile_name \\ subtiles \\ subtile_id

        :param stage: str representing which step you are at (subtiles, filtered, interpolated, ...)
        :param subtile_id: str or int representing the id of the subtile
        :param extension: str representing file extension (.las, .tif)
        :return: string containing full path of subtile
        """
        if self._tile_type == TileTypes.SUBTILE:
            split = self._tile_name.split("_")
            subtile_id = split[1]
            tile_name = split[0]
        else:
            tile_name = self._tile_name

        path = os.path.join(
            self._processing_path,
            tile_name,
            stage
        )

        create_path_if_not_exists(path)

        return os.path.join(
            path,
            subtile_id + "." + extension
        )

    def get_bottom_left(self):
        """ Gets all known filepaths for tiles in the left bottom. So: left, left-bottom, and bottom as these are all
        needed to get overlap for this corner.

        :return: List of all tile filepaths, or empty list if no adjacent exists
        """
        bottom_left = [
            neighbor.filepath for neighbor in [self._left, self._bottom_left, self._bottom] if neighbor is not None
        ]

        return bottom_left

    def get_bottom_right(self):
        """ Gets all known filepaths for tiles in the right bottom. So: right, right-bottom, and bottom as these are all
        needed to get overlap for this corner.

        :return: List of all tile filepaths, or empty list if no adjacent exists
        """

        bottom_right = [
            neighbor.filepath for neighbor in [self._right, self._bottom_right, self._bottom] if neighbor is not None
        ]

        return bottom_right

    def get_top_left(self):
        """ Gets all known filepaths for tiles in the left top. So: left, left-top, and top as these are all
        needed to get overlap for this corner.

        :return: List of all tile filepaths, or empty list if no adjacent exists
        """
        top_left = [
            neighbor.filepath for neighbor in [self._left, self._top_left, self._top] if neighbor is not None
        ]

        return top_left

    def get_top_right(self):
        """ Gets all known filepaths for tiles in the right top. So: right, right-top, and top as these are all
        needed to get overlap for this corner.

        :return: List of all tile filepaths, or empty list if no adjacent exists
        """
        top_right = [
            neighbor.filepath for neighbor in [self._right, self._top_right, self._top] if neighbor is not None
        ]

        return top_right

    def get_left(self):
        """ Returns tile to the left of this tile
        :return: List with tile filepath, or empty list if no adjacent exists
        """
        if self._left is not None:
            return [self._left.filepath]
        else:
            return []

    def get_right(self):
        """ Returns tile to the right of this tile
        :return: List with tile filepath, or empty list if no adjacent exists
        """
        if self._right is not None:
            return [self._right.filepath]
        else:
            return []

    def get_top(self):
        """ Returns tile to the top of this tile
        :return: List with tile filepath, or empty list if no adjacent exists
        """
        if self._top is not None:
            return [self._top.filepath]
        else:
            return []

    def get_bottom(self):
        """ Returns tile to the bottom of this tile
        :return: List with tile filepath, or empty list if no adjacent exists
        """
        if self._bottom is not None:
            return [self._bottom.filepath]
        else:
            return []
