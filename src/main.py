import datetime
import configparser
import os
import multiprocessing
import queue
import time

from src.task import Task
from src.utils.indexing import get_tile_connectivity

SPACING_INTERVAL = 1.0
WAIT_TIME_INTERVAL = 60


class MainProcessor:
    def __init__(self, tiles):
        """ Initializes the main processing class with a list of tile names for which the data should be processed.

        :param tiles: List containing strings representing names of tiles (e.g. ['36FN2', '31AZ1', ..]
        """
        self._processes = []
        self._processing = True
        self._target_tiles = tiles
        self._last_insertion = 0

        self._tile_connectivity = get_tile_connectivity()

        self._unprocessed_tiles = list(self._tile_connectivity.keys())

        self.task_queue = multiprocessing.Queue()
        self.in_progress_queue = multiprocessing.Queue()

        self._completed_dtm = multiprocessing.Manager().dict()
        self._completed_dsm = multiprocessing.Manager().dict()
        self.lock = multiprocessing.Lock()

    def create_new_split_tile_tasks(self):
        """ Creates new tasks for splitting tiles. Only creates as many split tile tasks as cores that have been
        specified in the config.

        :return: None
        """
        count = 0
        for parent_tile in self._target_tiles:
            if parent_tile in self._unprocessed_tiles:  # Dict would be faster here

                if count >= number_of_processing_threads:
                    break

                arguments = [self._tile_connectivity[parent_tile], self._tile_connectivity]
                new_task = Task(task="split_ahn3_tile", arguments=arguments)
                self.task_queue.put(new_task)

                self._unprocessed_tiles.remove(parent_tile)
                count += 1

    def _create_merge_task_for_tile(self, completed_tile_name: str, interpolation_type: str):
        """ Creates a merge rasters task used the supplied tile name and interpolation type. Relies on both these
        parameters because the completed_tiles variable contains both DTM and DSM data

        :param completed_tile_name: String representing the name of the tile that has been completed (e.g. 36FN2)
        :param interpolation_type: String representing interpolation type (dsm or dtm)
        :return: None
        """
        successfully_interpolated_tiles = []
        indexes_to_remove = []
        parent_tile = None

        if interpolation_type == "dtm":
            completed_tiles = self._completed_dtm
        else:
            completed_tiles = self._completed_dsm

        for tile_index in range(len(completed_tiles[completed_tile_name])):
            tile = completed_tiles[completed_tile_name][tile_index]

            if tile.interpolated is True and tile.related_raster is not None:
                parent_tile = tile
                successfully_interpolated_tiles.append(tile)

                indexes_to_remove.append(tile_index)

        if interpolation_type == "dtm":
            del self._completed_dtm[completed_tile_name]
        else:
            del self._completed_dsm[completed_tile_name]

        if parent_tile is not None:
            arguments = [parent_tile.get_parent_tile(), successfully_interpolated_tiles]
            self.task_queue.put(Task(task="merge_rasters", arguments=arguments))

    def start_processing_loop(self):
        """ Initiates as many threads as specified in the configuration
        :return: None
        """
        for process_id in range(number_of_processing_threads):
            process = multiprocessing.Process(
                name="Process-{0:02d}".format(process_id + 1),  # Pretty name for process for printing to commandline
                target=get_next_task,
                args=(self.task_queue, self.in_progress_queue, self._completed_dtm, self._completed_dsm, self.lock),
                daemon=True,
            )

            process.start()

            self._processes.append(process)

            time.sleep(SPACING_INTERVAL)

        while True:
            print("\n", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            print("Number of tasks available:", self.task_queue.qsize())
            print("Number of tasks in progress:", self.in_progress_queue.qsize())

            if self.task_queue.qsize() < number_of_processing_threads and time.time() - self._last_insertion > 3600:
                print("Creating more split tasks; (almost) done processing current tiles")
                self.create_new_split_tile_tasks()
                self._last_insertion = time.time()

            for tile_name in self._completed_dtm.keys():
                if len(self._completed_dtm[tile_name]) == num_cols_in_tile * num_rows_in_tile:
                    print("All interpolations completed for:", tile_name, "with type dtm")
                    self._create_merge_task_for_tile(tile_name, "dtm")

            for tile_name in self._completed_dsm.keys():
                if len(self._completed_dsm[tile_name]) == num_cols_in_tile * num_rows_in_tile:
                    print("All interpolations completed for:", tile_name, "with type dsm")
                    self._create_merge_task_for_tile(tile_name, "dsm")

            time.sleep(WAIT_TIME_INTERVAL)


def get_next_task(task_queue, in_progress_queue, completed_dtm, completed_dsm, lock):
    """ Retrieves a new task from the queue if there is one, otherwise idles until task is available or killed
    :return: None
    """
    try:
        task = task_queue.get()

        print('\n{0}: Executing task "{1}"'.format(
            multiprocessing.current_process().name,
            task.get_task_type(),
        ))

        # Abusing queue as a counter for number of tasks in progress
        # TODO: Replace with better method
        in_progress_queue.put("")

        start_time = time.time()
        result = task.execute()

        print('\n{0}: Ran task "{1}" in {2} seconds.'.format(
            multiprocessing.current_process().name,
            task.get_task_type(),
            str(round(time.time() - start_time, 2))
        ))

        if result is not None:
            if task.get_task_type() == "split_ahn3_tile":
                for tile in result:
                    task_queue.put(Task(task="interpolation", arguments=[tile, "dtm"]))
                    task_queue.put(Task(task="interpolation", arguments=[tile, "dsm"]))

            elif task.get_task_type() == "interpolation":

                tile = result[0]
                interpolation_type = result[1]

                tile_name = tile.get_tile_name().split("_")[0]

                with lock:
                    if interpolation_type == "dsm":
                        if tile_name not in completed_dsm.keys():
                            completed_dsm[tile_name] = [tile]
                        else:
                            completed_dsm[tile_name] += [tile]
                    else:
                        if tile_name not in completed_dtm.keys():
                            completed_dtm[tile_name] = [tile]
                        else:
                            completed_dtm[tile_name] += [tile]

            elif task.get_task_type() == "merge_rasters":

                task_queue.put(Task(task="downsampling", arguments=[result]))

        # Ensure queue counter is subtracted again
        in_progress_queue.get()

        time.sleep(SPACING_INTERVAL)

    except queue.Empty:  # No items in queue, so idle
        print('\n{0}: Idling; no tasks available'.format(
            multiprocessing.current_process().name,
        ))

        time.sleep(WAIT_TIME_INTERVAL)

    finally:
        get_next_task(task_queue, in_progress_queue, completed_dtm, completed_dsm, lock)


if __name__ == "__main__":
    """ Entry point for the application, uses the files found in the folder specified in the config under folder path ->
    tiles to process as input. Will use the filenames of the files in these folders to create the new tasks. Also starts
    the processing loop and remains active as parent for all child processes.
    """
    directory = os.path.dirname(os.path.realpath(__file__))

    config = configparser.ConfigParser()
    config.read(os.path.join(directory, "config.ini"))

    number_of_processing_threads = int(config["global"]["number_of_processing_threads"])

    num_cols_in_tile = int(config["tile_parameters"]["subtile_column_count"])
    num_rows_in_tile = int(config["tile_parameters"]["subtile_row_count"])

    tile_path = config["folder_paths"]["tiles_to_process"]

    # Assuming format C_37HN1.LAZ, so splitting to 37HN1
    target_tiles = [f.split(".")[0].split("_")[1] for f in os.listdir(tile_path) if ".LAZ" in f or ".laz" in f]

    if len(target_tiles) == 0:
        raise Exception("Could not find any LAZ files with expected format in the specified folder! (C_37EN1.LAZ")

    print("Target tiles:", target_tiles)

    processor = MainProcessor(tiles=target_tiles)

    processor.start_processing_loop()
