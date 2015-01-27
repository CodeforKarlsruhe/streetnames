#!/usr/bin/env python
# vim: set fileencoding=utf-8 :

"""
Script to extract data from Karlsruhe street names text.

Takes ``strassennamen.txt`` and outputs ``raw_data.json``.
"""

from __future__ import unicode_literals

import codecs
import json
import os
import re

if __name__ == '__main__':

    # Load text
    HERE = os.path.dirname(os.path.abspath(__file__))
    TXT = os.path.join(HERE, 'strassennamen.txt')
    with codecs.open(TXT, 'r', encoding='utf8') as f:
        text = f.read()

    # Trim lines
    lines = text.split('\n')
    text = '\n'.join(line.strip() for line in lines)

    # Extract data
    streets = {}
    paragraphs = re.split(r'\n\n+', text)
    for para in paragraphs:
        lines = para.split('\n')
        if lines[0].strip().lower().startswith('liegenschaftsamt'):
            # Header
            continue
        if len(lines[0].strip()) == 1:
            # Single letter is a section header
            continue

        m = re.match(r'([^\d,]+)\D*(\d\d\d\d)?', lines[0], re.UNICODE)
        if not m:
            continue
        g = m.groups()
        street = g[0].strip()
        if g[1]:
            year = int(g[1])
        else:
            print 'WARNING: No year for "%s".' % street
            year = None

        d = {
            'info': '\n'.join(lines[1:]),
        }
        if year:
            d['year'] = year

        streets[street] = d

    # Store data
    JSON = os.path.join(HERE, 'raw_data.json')
    with codecs.open(JSON, 'w', encoding='utf8') as f:
        json.dump(streets, f, sort_keys=True, indent=4, separators=(',', ': '))
