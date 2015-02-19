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
Script to prepare individual datasets from complete data.

Takes ``streetnames.geojson`` and outputs various JSON files.
"""

from __future__ import unicode_literals

import codecs
import json
import os.path
import re

import geojson


if __name__ == '__main__':
    HERE = os.path.dirname(os.path.abspath(__file__))
    WEB = os.path.join(HERE, '..', 'web')
    SOURCE = os.path.join(WEB, 'streetnames.geojson')

    with codecs.open(SOURCE, 'r', encoding='utf8') as f:
        data = geojson.load(f)
    features = {}
    for feature in data['features']:
        features[feature.id] = feature

    def save(data, basename):
        filename = os.path.join(WEB, basename)
        with codecs.open(filename, 'w', encoding='utf8') as f:
            geojson.dump(data, f)

    def select(fun):
        return [f for f in features.itervalues() if fun(f['properties'])]

    #
    # Gender
    #
    dataset = [
        {
            'features': select(lambda p: p.get('gender') == 'm'),
            'label': 'männlich',
            'color': '#ff7f00',
        },
        {
            'features': select(lambda p: p.get('gender') == 'f'),
            'label': 'weiblich',
            'color': '#007fff',
        },
    ]
    save(dataset, 'gender.json')
