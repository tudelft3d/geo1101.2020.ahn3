import fiona
import numpy as np

import skgeom as sg

from shapely.geometry import MultiLineString, LineString
import csv
import sys

#solves csv data problem
maxInt = sys.maxsize
while True:
    # decrease the maxInt value by factor 10
    # as long as the OverflowError occurs.
    try:
        csv.field_size_limit(maxInt)
        break
    except OverflowError:
        maxInt = int(maxInt/10)

#make the skeleton function
file = open('old_csv/skeletons_big_river.csv', 'w')
with file:
    writer = csv.writer(file)
    add = [["id", "wkt"]]
    writer.writerows(add)
    with fiona.open('river_bodies/bbg_one_river_done.shp') as rivers:
        count = 0
        for feature in rivers:
            count += 1
            print("started on new river", count, "length ", len(feature['geometry']['coordinates'][0][0]), len(feature['geometry']['coordinates'][0]))
            if count >= 1:
                coord = feature['geometry']['coordinates']

                if len(feature['geometry']['coordinates'][0][0])> 2:
                    line = LineString(coord[0][0])
                    array_coord = np.array(coord[0][0][1:])

                    square = sg.Polygon(array_coord)
                    area= square.area()
                    print(area)

                    hole_list = []
                    for hole in coord[0][1:]:
                        tri = sg.Polygon(hole)
                        area = tri.area()
                        print(area)
                        hole_list.append(hole[1:][::-1])
                    poly = sg.PolygonWithHoles(array_coord[::-1],hole_list)

                else:
                    line = LineString(coord[0])
                    array_coord = np.array(coord[0][1:-1])
                    poly = sg.Polygon(array_coord)

                    #check if the polygon is ccw
                    if poly.area() < 0:
                        poly = sg.Polygon(array_coord[::-1])

                #make the skeleton
                skel = sg.skeleton.create_interior_straight_skeleton(poly)
                print("skeleton made")

                #add line parts to multiline if correct
                lines = []
                for edge in skel.halfedges:
                    if edge.is_bisector:
                        p1 = edge.vertex.point
                        p2 = edge.opposite.vertex.point

                        #check if it goes to the boundary of the polygon (get rid of side branches)
                        linestring = LineString(((p1.x(), p1.y()),(p2.x(), p2.y())))
                        if not linestring.intersects(line):
                            lines.append(linestring)
                        # coordinates.append(((p1.x(), p1.y()),(p2.x(), p2.y())))

                skeleton = MultiLineString(lines)
                add = [[count,skeleton.wkt]]
                writer.writerows(add)



