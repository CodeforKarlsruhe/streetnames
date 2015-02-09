#!/usr/bin/env python
# vim: set fileencoding=utf-8 :

# Copyright (c) 2015 Code for Karlsruhe (http://codefor.de/karlsruhe)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

"""
Script to extract street coordinates from OSM data.

Takes ``highways.osm`` and outputs data into ``streets.geojson``.
"""

from __future__ import unicode_literals

import codecs
import collections
import json
import os.path

import geojson
from lxml import etree


def parse_osm(f):
    """
    Extract street coordinates from OSM file.
    """
    # Extract node references
    streets = collections.defaultdict(lambda: [])
    nodes = {}
    node_refs = []
    tags = {}
    for event, element in etree.iterparse(f):
        if element.tag == 'node':
            nodes[element.get('id')] = (float(element.get('lon')),
                                        float(element.get('lat')))
            tags = {}
        elif element.tag == 'tag':
            tags[element.get('k')] = element.get('v')
        elif element.tag == 'nd':
            node_refs.append(element.get('ref'))
        elif element.tag == 'way':
            streets[tags['name']].append(node_refs)
            tags = {}
            node_refs = []

    # Resolve node references
    for name, ways in streets.iteritems():
        resolved_ways = []
        for way in ways:
            try:
                resolved_ways.append([nodes[ref] for ref in way])
            except KeyError:
                pass
        ways[:] = resolved_ways

    # Remove empty streets
    streets = {name: ways for name, ways in streets.iteritems() if ways}

    return streets


def ways2geometry(ways):
    """
    Convert a nested list of coordinates into a GeoJSON object.
    """
    if len(ways) == 1:
        return geojson.LineString(ways[0])
    else:
        return geojson.MultiLineString(ways)


if __name__ == '__main__':
    HERE = os.path.dirname(os.path.abspath(__file__))
    OSM = os.path.join(HERE, 'karlsruhe.osm')
    GEOJSON = os.path.join(HERE, 'coordinates.geojson')

    with open(OSM, 'r') as f:
        streets = parse_osm(f)

    features = []
    for name, ways in streets.iteritems():
        features.append(geojson.Feature(geometry=ways2geometry(ways),
                        id=name))
    collection = geojson.FeatureCollection(features)

    with codecs.open(GEOJSON, 'w', encoding='utf8') as f:
        geojson.dump(collection, f)
