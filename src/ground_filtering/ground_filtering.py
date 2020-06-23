import configparser
import json
import os

import pdal

from src.tile import Tile
from src.utils.helpers import Stages

# TODO: Move to better location; want to prevent loading every time it is run, but keeping it here is strange
GROUND_FILTERING_DTM = [
    {
        "type": "filters.elm"
    },
    {
        "type": "filters.outlier"
    },
    {
        "type": "filters.range",
        "limits": "Classification[2:2]"
    }
]

GROUND_FILTERING_DSM = [
    {
        "type": "filters.elm"
    },
    {
        "type": "filters.outlier"
    },
    {
        "type": "filters.range",
        "limits": "Classification![7:7]"
    }
]


class GroundFiltering:
    def __init__(self, input_tile: Tile):
        self._tile = input_tile

        directory = os.path.dirname(os.path.realpath(__file__))

        config = configparser.ConfigParser()
        config.read(os.path.join(directory, "..", "config.ini"))

        self._to_overwrite = True if config["global"]["overwrite_existing_files"] == "true" else False

    def remove_outliers(self, stage: Stages):
        """ Remove outliers current input tile

        :return: Array containing filtered raster result
        """
        if stage == Stages.INTERPOLATED_DSM:
            pdal_config = GROUND_FILTERING_DSM.copy()  # Copy to avoid changing original config

        else:
            pdal_config = GROUND_FILTERING_DTM.copy()  # Copy to avoid changing original config

        # Insert the filepath of this specific file in the pipeline
        pdal_config.insert(0, self._tile.filepath)

        # pdal_config.append(save_name) # Appends the correct save path for this tile and stage

        pipeline = pdal.Pipeline(json.dumps(pdal_config))  # .dumps() to go from json to str

        pipeline.execute()

        return pipeline.arrays
