# Improved AHN3 Gridded DTM/DSM

<img src="data/images/comparison_old_new.gif" height="400px" alt="Comparison between current DTM and improved version"/>  

---

The current gridded DTM and DSM for the Netherlands has some flaws, showing many missing pixels where the interpolation
method was unable to determine a value, and has holes where buildings and water bodies were removed from the dataset.

The goal of this project is to improve upon the results available by creating DSM/DTM results that no longer have no-data
values. This creates rasters with complete coverage of their target area, ensuring that every pixel value has an accurate
height assigned to it.

This has mainly been made possible by the following Python packages and binaries:  

- [Startin](https://github.com/hugoledoux/startin_python)
- [las2las](https://rapidlasso.com/lastools/las2las/)
- [rasterio](https://rasterio.readthedocs.io/en/latest/)
- [shapely](https://shapely.readthedocs.io/en/latest/manual.html)
- [PDAL](https://pdal.io/)
- [GDAL](https://gdal.org/)
- [Laspy](https://laspy.readthedocs.io/en/latest/)


## Usage

The tool is made to run an amount of threads in parallel to ensure fast processing. Please note that each thread needs
around 20GB of memory to run. Optimizations can be made if memory use for quadrant-based IDW is reduced, and/or for Startin.

1. Install all packages specified in [requirements.txt](requirements.txt)
1. Configure your settings in the [config.ini](config.ini)
    1. Global parameters and folder paths are essential to change
    1. Further parameters are optimized for use with AHN3 dataset
1. Run main.py

## Notes
For DTM a Laplace interpolation is used based on Startin's Delaunay Triangulation, which in turn is based on Rust, making
it extremely fast to execute.

For DSM a quadrant-based IDW is used, which is implemented in Python. This method is limited by the amount of raster cells
it needs to interpolate for and the speed at which Python can do so. Depending on how small your base raster cell size is
this will take a while to run.

Error handling is partially implemented; no errors should occur that will break the processing loop, though some of
these errors may result in partial outcomes.

Some of the files include a NO_DATA value defined at the top of the file as -9999, if this needs changing this is where
to find it.

## Troubleshooting  

- PDAL/GDAL won't install for various reasons
    - Start from a clean Python 3.7 Anaconda virtual environment
    - First install PDAL and GDAL, then the other requirements

## Contributors
![Contributors](data/images/contributors.svg)


