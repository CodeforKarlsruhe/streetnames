#!/bin/bash

# Extract highways from OSM data that are within the boundary of the
# city of Karlsruhe. The data is stored in `highways.osm`.
#
# Requires the `osmosis` tool.


#
# Download data if necessary
#

DIR=http://download.geofabrik.de/europe/germany/baden-wuerttemberg
BASE=karlsruhe-regbez-latest.osm.pbf

if [ -f "${BASE}" ]; then
    # Download MD5 file to see if file is up-to-date
    echo "${BASE} exists, downloading MD5 to check whether it's up to date."
    wget -q -N ${DIR}/${BASE}.md5 -O ${BASE}.md5
    LATEST_MD5=$(<${BASE}.md5)
    FILE_MD5=`md5sum ${BASE}`
    if [ "$LATEST_MD5" == "$FILE_MD5" ]; then
        echo "File is up to date."
    else
        echo "File is outdated, downloading latest version."
        wget ${DIR}/${BASE}
    fi
else
    echo "${BASE} doesn't exist, downloading it."
    wget ${DIR}/${BASE}
fi


#
# Extract highway information
#

osmosis --read-pbf file=${BASE} \
        --bounding-polygon file=karlsruhe.poly \
        --way-key keyList=highway \
        --way-key keyList=name \
        --tag-filter reject-relations \
        --used-node idTrackerType=Dynamic \
        --write-xml highways.osm
