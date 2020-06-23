import configparser
import os
import gdal

from src.raster import Raster


class DownSampling:
    def __init__(self, input_raster: Raster):
        """ Configures the variables needed to downsample a raster from current size to the crude size specified in
        config.

        :param input_raster: Raster object of the raster for which downsampling is required
        """
        self._raster = input_raster

        directory = os.path.dirname(os.path.realpath(__file__))

        config = configparser.ConfigParser()
        config.read(os.path.join(directory, "..", "config.ini"))

        self._raster_cell_size = float(config["global"]["crude_raster_cell_size"])

    def downsample(self):
        """ Function that uses GDAL's warp function to downsample a raster

        :return: None
        """
        input_raster = self._raster.filepath
        output_raster = self._raster.get_downsampled_save_location()

        gdal.Warp(
            output_raster,
            input_raster,
            outputType=gdal.GDT_Float32,
            xRes=self._raster_cell_size,
            yRes=self._raster_cell_size
        )

