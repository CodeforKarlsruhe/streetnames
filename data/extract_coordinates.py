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


# Streets are straightforward: They are stored as "way" objects in OSM
# and have a "highway" and a "name" tag. The only non-trivial thing is
# that a street may consist of several "way" objects.
#
# Places, on the other hand, have no canonical representation in OSM.
# Here is a list of example places from Karlsruhe:
#
#    Relation: Friedrichsplatz (1542213)
#        leisure: park
#        type: multipolygon
#
#    Way: Gotthold-Mayer-Platz (182377023)
#        leisure: park
#
#    Way: Schlossplatz (162432233)
#        area: yes
#        highway: pedestrian
#
#    Relation: Lidellplatz (2227646)
#        area: yes
#        highway: pedestrian
#        type: multipolygon
#
#    Relation: Mendelssohnplatz (4552741)
#        highway: pedestrian
#        type: multipolygon
#
#    Way: Engländerplatz (26723820)
#        leisure: pitch
#
#    Way: Fliederplatz (4835450)
#        leisure: common
#
#    Node: Paulckeplatz (1673718306)
#        highway: place


def check(d, k, v):
    """
    Check if d[k] == v.
    """
    try:
        return d[k] == v
    except KeyError:
        return False


def parse_osm(f):
    """
    Extract coordinates from OSM file.
    """
    relations = {}
    ways = {}
    nodes = {}
    highway_nodes = {}
    node_refs = []
    tags = {}
    members = []
    for event, element in etree.iterparse(f):
        if element.tag == 'node':
            coords = (float(element.get('lon')), float(element.get('lat')))
            if 'name' in tags and check(tags, 'highway', 'place'):
                tags['coordinates'] = [coords]
                highway_nodes[tags['name']] = tags
            nodes[element.get('id')] = coords
            tags = {}
        elif element.tag == 'tag':
            tags[element.get('k')] = element.get('v')
        elif element.tag == 'nd':
            node_refs.append(element.get('ref'))
        elif element.tag == 'way':
            d = {'nodes': node_refs}
            d.update(tags)
            ways[element.get('id')] = d
            tags = {}
            node_refs = []
        elif element.tag == 'relation':
            name = tags.get('name')
            if name and (check(tags, 'leisure', 'park') or
                    (check(tags, 'highway', 'pedestrian') and
                    check(tags, 'type', 'multipolygon'))):
                d = {'members': members}
                d.update(tags)
                if name in relations:
                    raise ValueError('Duplicate relation "%s".' % name)
                relations[name] = d
            tags = {}
            members = []
        elif element.tag == 'member':
            members.append(dict(element.attrib))
        element.clear()

    # Resolve node references in ways
    for id, props in ways.iteritems():
        try:
            props['coordinates'] = [nodes[ref] for ref in props['nodes']]
        except KeyError:
            pass

    # Resolve inner/outer members of multipolygon relations
    for id, props in relations.iteritems():
        if check(props, 'type', 'multipolygon'):
            props['inner'] = []
            props['outer'] = []
            for member in props['members']:
                role = member.get('role', 'outer')
                if role in ['inner', 'outer']:
                    props[role].append(ways[member['ref']])

    # Extract streets
    streets = collections.defaultdict(lambda: [])
    for way in ways.itervalues():
        if ('name' in way) and ('coordinates' in way):
            if ('highway' in way) or way.get('leisure') in ['park', 'pitch', 'common']:
                streets[way['name']].append(way)

    return streets, relations, highway_nodes


def ways2geometry(ways):
    """
    Convert a nested list of coordinates into a GeoJSON object.
    """
    if len(ways) == 1:
        way = ways[0]
        highway = way.get('highway')
        if ((way.get('area', '') == 'yes' and highway == 'pedestrian') or
                (way.get('leisure') in ['park', 'pitch', 'common'])):
            # See http://wiki.openstreetmap.org/wiki/Key:area
            return geojson.Polygon([way['coordinates']])
        elif highway:
            return geojson.LineString(way['coordinates'])
    else:
        return geojson.MultiLineString([w['coordinates'] for w in ways])


def relation2geometry(relation):
    """
    Convert relation data into a GeoJSON object.
    """
    if check(relation, 'type', 'multipolygon'):
        outer = relation['outer']
        inner = relation['inner']
        if not inner:
            return geojson.MultiPolygon([(o['coordinates'],) for o in outer])
        if len(outer) == 1:
            polygons = [outer[0]['coordinates']]
            for way in inner:
                polygons.append(way['coordinates'])
            return geojson.MultiPolygon([polygons])
        raise ValueError('Unknown inner/outer configuration %r' % relation)
    else:
        raise ValueError('Unknown relation type %r' % relation)


def node2geometry(node):
    """
    Convert node data into a GeoJSON object.
    """
    return geojson.Point(node['coordinates'][0])


if __name__ == '__main__':
    HERE = os.path.dirname(os.path.abspath(__file__))
    OSM = os.path.join(HERE, 'karlsruhe.osm')
    GEOJSON = os.path.join(HERE, 'coordinates.geojson')

    with open(OSM, 'r') as f:
        streets, relations, nodes = parse_osm(f)

    features = []
    for name, ways in streets.iteritems():
        features.append(geojson.Feature(geometry=ways2geometry(ways),
                        id=name))
    for name, props in relations.iteritems():
        features.append(geojson.Feature(geometry=relation2geometry(props),
                        id=name))
    for name, props in nodes.iteritems():
        features.append(geojson.Feature(geometry=node2geometry(props),
                        id=name))
    collection = geojson.FeatureCollection(features)

    with codecs.open(GEOJSON, 'w', encoding='utf8') as f:
        geojson.dump(collection, f)
