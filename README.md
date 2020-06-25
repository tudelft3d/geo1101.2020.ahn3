[![GitHub license](https://img.shields.io/github/license/tudelft3d/geo1101.2020.ahn3)](https://github.com/tudelft3d/geo1101.2020.ahn3/blob/master/LICENSE) [![DOI](https://zenodo.org/badge/273226804.svg)](https://zenodo.org/badge/latestdoi/273226804) [![Documentation Status](https://readthedocs.org/projects/geo11012020ahn3/badge/?version=latest)](https://geo11012020ahn3.readthedocs.io/en/latest/?badge=latest)

# Improved AHN3 Gridded DTM/DSM

<img src="data/images/comparison_old_new.gif" height="400px" alt="Comparison between current DTM and improved version"/>  

<sub>GIF created using [JuxtaposeJS](https://juxtapose.knightlab.com/) </sub>

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

## Documentation and help
Read the full documentation at [http://geo11012020ahn3.rtfd.io/](http://geo11012020ahn3.rtfd.io/)

For any hiccups you encounter, please create an [issue](https://github.com/tudelft3d/geo1101.2020.ahn3/issues/new)

## Notes
For more interpolation methods that have been implemented in the process of this project, see
[this](https://github.com/khalhoz/AHN-GroundFiltering-and-Interpolation) repository. It holds six different interpolation
methods that can be used to replace the ones featured here, and also contains information on how to use them.

The chosen interpolation methods in this repository have been proven to provide the best results for our datasets, and are
the most robust encountered.

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
<a href="https://github.com/khalhoz"><img src="https://avatars3.githubusercontent.com/u/45310130?s=400&v=4" alt="k  halhoz" height="75px" style="border-radius:20px"></a>
<a href="https://github.com/kriskenesei"><img src="https://avatars1.githubusercontent.com/u/33285109?s=400&v=4" alt="kriskenesei" height="75px" style="border-radius:20px"></a>
<a href="https://github.com/mdjong1"><img src="https://avatars3.githubusercontent.com/u/4410453?s=460&u=237764227f8e0120c09d1ee7ba68a8ec05de57b5&v=4" alt="mdjong1" height="75px" style="border-radius:20px"></a>
<a href="https://github.com/lkeurentjes"><img src="https://avatars1.githubusercontent.com/u/43202623?s=460&u=4444f9995c4524bf129ae418df178a7a55d19d1b&v=4" alt="lkeurentjes" height="75px" style="border-radius:20px"></a>
<a href="https://github.com/mpa-tudelft"><img src="https://avatars2.githubusercontent.com/u/63740918?s=460&v=4" alt="mpa-tudelft" height="75px" style="border-radius:20px"></a>
<a href="https://github.com/hugoledoux"><img src="https://avatars3.githubusercontent.com/u/1546518?s=460&u=d2e1fa9dabc69e71793739e739f6bac7ce24a1b9&v=4" alt="hugoledoux" height="75px" style="border-radius:20px"></a>

