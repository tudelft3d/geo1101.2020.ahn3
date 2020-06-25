import fiona

# Open a file for reading. We'll call this the "source."

with fiona.open('BBG download/BBG2015.shp') as src:
    # we safe the metadata as parameter, seeing we want to re-use those in the sub files
    meta = src.meta

    # Open the output files, using the same format driver and coordinate reference system as the source (**meta).
    with fiona.open('river_bodies/bbg_only_river_bodies.shp', 'w', **meta) as river:
        with fiona.open('sea_bodies/bbg_sea_and_big_bodies.shp', 'w', **meta) as sea:
            with fiona.open('rest_bodies/bbg_rest_of_the_water.shp', 'w', **meta) as overig:
                for feature in src:
                    if feature['properties']['Hoofdgroep'] == 'Water':
                        if feature['properties']['Omschrijvi'] == 'Rijn & Maas':
                            river.write(feature)
                        elif feature['properties']['Omschrijvi'] == 'IJsselmeer/Markermeer' \
                                or feature['properties']['Omschrijvi'] == 'Afgesloten zeearm'\
                                or feature['properties']['Omschrijvi'] == 'Noordzee' \
                                or feature['properties']['Omschrijvi'] == 'Oosterschelde' \
                                or feature['properties']['Omschrijvi'] == 'Waddenzee, Eems, Dollard' \
                                or feature['properties']['Omschrijvi'] == 'Westerschelde'\
                                or feature['properties']['Omschrijvi'] == 'Randmeer':
                            sea.write(feature)
                        else:
                            overig.write(feature)

