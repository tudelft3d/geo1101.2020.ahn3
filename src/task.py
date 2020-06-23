import multiprocessing

from src.downsampling.downsampling import DownSampling
from src.interpolation.interpolation import Interpolation
from src.merging.merging import Merging
from src.raster import Raster
from src.subtiling.subtiling import Subtiling


# TODO: Add TaskTypes

class Task:
    def __init__(self, task: str, arguments: list):
        """ Class to route where a task is sent to and how it is pre- and post-processed.

        Takes specific task types as input with their arguments. Then depending on this task type it routes the
        arguments to the correct function. Also the place to put subsequent steps, as can be seen after splitting
        where the ground filtering task is queued, as this is now possible because subtiling has completed.

        :param task: String representing the task to execute
        :param arguments: List representing the arguments to input into the task
        """

        # FIXME: Improve this "ENUM"
        self._task_types = {
            "split_ahn3_tile": self._split_ahn3_tile,
            "interpolation": self._interpolation,
            "merge_rasters": self._merge_rasters,
            "downsampling": self._downsampling,
        }

        self._task = task
        self._arguments = arguments

        if self._task not in self._task_types.keys():
            print("Chosen a task that I don't know")

    def get_task_type(self):
        return self._task

    @staticmethod
    def _split_ahn3_tile(input_arguments: list):
        """ Function that creates a Subtiling class, gets extents, divides the tile, and creates and stores child tiles.
        Also creates new tasks for subsequent step (ground filtering)

        :param input_arguments: List containing the tile object as element 0 and the tile connectivity as element 1
        :return: None
        """
        subtiling = Subtiling(tile=input_arguments[0], connectivity=input_arguments[1])

        subtiling.set_tile_extents()
        subtiling.subdivide_tile()
        subtiling.clip_tile_by_subtiles()

        return subtiling.get_created_subtiles()

    @staticmethod
    def _interpolation(input_arguments: list):
        """ Function that creates an Interpolation class and runs the interpolation pipeline in the chosen format.
        Also runs a ground filtering step as part of the pipeline.

        :param input_arguments: List containing Tile object as 0th element and interpolation result type as 1st element
        :return: Tile object of completed tile, string representing type of interpolation that has been completed
        """
        subtile = input_arguments[0]
        interpolation_type = input_arguments[1]

        interpolation = Interpolation(input_tile=subtile, result_type=interpolation_type)

        interpolation.interpolate()

        return subtile, interpolation_type

    @staticmethod
    def _merge_rasters(input_arguments: list):
        """ Function that clips all the input raster tiles, then feeds these to the Merging class to be merged and saved
        to disk in the 'finished' folder from the config.

        :param input_arguments: List containing Tile object as 0th element which represents the parent tile, 1st element
        is which child tiles were successfully interpolated
        :return: None
        """
        input_tile = input_arguments[0]
        tiles_to_merge = input_arguments[1]

        raster = None

        indexes_to_remove = []

        for subtile_index in range(len(tiles_to_merge)):
            # Clip each raster with the relevant subtile to ensure size of clipped raster is correct
            raster = tiles_to_merge[subtile_index].related_raster

            if raster.clip(tile=tiles_to_merge[subtile_index]) is False:
                # Failed to clip raster, remove from merge list
                indexes_to_remove.append(subtile_index)

        for index in indexes_to_remove:
            del tiles_to_merge[index]

        rasters_to_merge = [subtile.related_raster for subtile in tiles_to_merge]

        merging = Merging(tile=input_tile, input_rasters=rasters_to_merge)

        try:
            merging.merge_rasters()

            output_name, output_filepath = merging.save(stage=raster.get_stage())

            output_raster = Raster(raster_name=output_name, filepath=output_filepath, stage=raster.get_stage())

            output_raster.homogenize_patchwork()

            return output_raster

        except Exception as e:
            print('\n{0}: Merging failed with error:'.format(
                multiprocessing.current_process().name,
                str(e)
            ))

    @staticmethod
    def _downsampling(input_arguments: list):
        """ Function that downsamples the raster from it's current level to the crude level specified
        in config. In general that is from 0.5m cell size to 5m cell size. Relies on the DownSampling class. Saves the
        output with the correct name to the same folder.

        :param input_arguments: List containing 1 element which is a Raster class representing the Raster to downsample
        :return: None
        """
        input_raster = input_arguments[0]

        downsampling = DownSampling(input_raster=input_raster)

        downsampling.downsample()

    def execute(self):
        """ Function called by a thread when it is ready to run its next task, ensures functions and arguments are
        routed correctly.

        :return: Result from executed task, differs depending on task being executed
        """
        try:
            return self._task_types[self._task](self._arguments)
        except Exception as e:
            raise
