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
Script to merge street coordinates and name information.

Takes ``streets.geojson`` and ``streetnames.json`` and outputs
``streetnames.geojson``.
"""

from __future__ import unicode_literals

import codecs
import json
import os.path
import re

import geojson


def normalize_name(n):
    """
    Normalize street name.

    The names of many streets are spelled slightly different in our
    different data sources. This function tries to reduce these
    differences.
    """
    n = n.lower().replace('-', ' ').replace('ß', 'ss').strip()
    return re.sub(r'\s+', ' ', n)


if __name__ == '__main__':
    HERE = os.path.dirname(os.path.abspath(__file__))
    NAMES = os.path.join(HERE, 'streetnames.json')
    COORDINATES = os.path.join(HERE, 'streets.geojson')
    MERGED = os.path.join(HERE, 'streetnames.geojson')

    with codecs.open(COORDINATES, 'r', encoding='utf8') as f:
        coordinates = geojson.load(f)
    features = {}
    for feature in coordinates['features']:
        features[normalize_name(feature.id)] = feature

    with codecs.open(NAMES, 'r', encoding='utf8') as f:
        names = json.load(f)
    for name, props in names.iteritems():
        if not (props['year'] or props['previous'] or props['info']):
            print 'No information about "%s"' % name
            continue
        try:
            feature = features[normalize_name(name)]
            feature.properties = props
        except KeyError:
            print 'Could not find coordinates for "%s"' % name

    collection = geojson.FeatureCollection(features.values())
    with codecs.open(MERGED, 'w', encoding='utf8') as f:
        geojson.dump(collection, f)
