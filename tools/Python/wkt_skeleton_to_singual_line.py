import csv
import fiona
from shapely.geometry import Point, LineString, box, Polygon, MultiLineString, LinearRing
import sys
import shapely.wkt

#make max data for csv better
maxInt = sys.maxsize
while True:
    # decrease the maxInt value by factor 10
    # as long as the OverflowError occurs.
    try:
        csv.field_size_limit(maxInt)
        break
    except OverflowError:
        maxInt = int(maxInt/10)

# the script itself
wf = open('skeletons_simple_line.csv', 'w')
with wf:
    writer = csv.writer(wf)
    add = [["id", "wkt"]]
    writer.writerows(add)
    with fiona.open('river_bodies/bbg_one_river_done.shp') as rivers:
        count = 0
        for feature in rivers:
            count +=1
            coord = feature['geometry']['coordinates']
            if count == 1:
                polies = []
                for co in coord[0][1:]:
                    hole = LinearRing(co)

                    polies.append(hole)
                poly = Polygon(coord[0][0], polies)
                print(poly)
            else:
                poly = LineString(coord[0])

            with open('old_csv/skeletons_big_river.csv', newline='') as file:
                reader = csv.reader(file, delimiter=",")
                firstline = True
                for row in reader:
                    if firstline:
                        firstline = False
                    elif len(row) > 0:
                        if int(row[0]) == count:
                            multiline = shapely.wkt.loads(row[1])
                            lines = []
                            for line in multiline:
                                if count == 1:
                                    if line.within(poly.buffer(-10)): # or not line.intersects(poly) :
                                        lines.append(line)
                                elif count ==2:
                                    if not line.intersects(poly.buffer(1)):
                                        lines.append(line)
                                else:
                                    if not line.intersects(poly.buffer(5)):
                                        lines.append(line)
                            single_line = MultiLineString(lines)
                            print(single_line)
                            add =[[count, single_line.wkt]]
                            writer.writerows(add)