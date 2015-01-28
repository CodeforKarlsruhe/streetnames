#!/usr/bin/env python
# vim: set fileencoding=utf-8 :

"""
Parse HTML export of ``strassennamen.pdf``.

Requires ``strassennamen.html``, generated using pdf2htmlEX_ via
``pdf2htmlEX strassennamen.pdf``. Produces ``raw_data.json``.

.. _pdf2htmlEX: https://github.com/coolwanglu/pdf2htmlEX
"""

from __future__ import unicode_literals

import codecs
import json
import os.path
import re

import bs4


def parse_header(s):
    """
    Parse an entry header into the street name and year.
    """
    m = re.match(r'([^\d,]+)\D*(\d\d\d\d)?', s)
    if not m:
        return (None, None)
    g = m.groups()
    street = g[0].strip()
    year = int(g[1]) if g[1] else None

    # Sometimes there is additional stuff behind the street name,
    # e.g. "Unterer Lichtenbergweg in den 1970". That stuff always
    # is all lowercase.
    parts = list(reversed(street.split()))
    if len(parts) > 1:
        for i in range(len(parts)):
            if not parts[i].islower():
                break
        street = ' '.join(reversed(parts[i:]))

    return (street, year)


def tag_text(t):
    """
    Get a tag's text, including that of nested tags.
    """
    return ''.join(t.strings).strip()


if __name__ == '__main__':

    HERE = os.path.dirname(os.path.abspath(__file__))
    HTML = os.path.join(HERE, 'strassennamen.html')
    JSON = os.path.join(HERE, 'raw_data.json')

    with open(HTML) as f:
        soup = bs4.BeautifulSoup(f.read())

    streets = []
    current = None
    for div in soup.find_all(id='page-container')[0].find_all('div'):
        classes = div.attrs.get('class', [])
        if not 't' in classes:
            # Structuring div
            continue
        text = tag_text(div)
        if not text:
            continue
        if 'ff1' in classes:
            # Bold text, entry header
            if text in ['Liegenschaftsamt', 'Straßennamen in Karlsruhe']:
                continue
            if len(text) == 1:
                # Letter header
                continue
            if current:
                streets.append(current)
            current = {'name': '', 'year': None, 'previous': '', 'info': ''}
            current['name'], current['year'] = parse_header(text)
        elif 'm1' in classes:
            # Italic text, contains previous street names
            if current['previous']:
                current['previous'] += ' '
            current['previous'] += text
        else:
            # Normal text
            if current['info']:
                current['info'] += ' '
            current['info'] += text
    if current:
        streets.append(current)

    with codecs.open(JSON, 'w', encoding='utf8') as f:
        json.dump(streets, f, sort_keys=True, indent=4, separators=(',', ': '))

