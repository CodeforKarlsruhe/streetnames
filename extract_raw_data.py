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


def parse_previous(s):
    """
    Parse list of previous street names.
    """
    if not s.strip():
        return []
    entries = []
    parts = re.split(r'[,;/]', s)
    for part in parts:
        part = part.strip()
        m = re.match(r'(?:bzw\.\s*)?(?:ca\.\s*)?(?:um\s*)?(\d\d\d\d?)\s+(.*)', part)
        if m:
            g = m.groups()
            entries.append((int(g[0]), g[1].strip()))
        else:
            entries.append((None, part))
    return entries


def tag_text(t):
    """
    Get a tag's text, including that of nested tags.
    """
    return ''.join(t.strings).strip()


if __name__ == '__main__':
    HERE = os.path.dirname(os.path.abspath(__file__))
    HTML = os.path.join(HERE, 'strassennamen.html')
    JSON = os.path.join(HERE, 'raw_data.json')

    with codecs.open(HTML, 'r', encoding='utf8') as f:
        soup = bs4.BeautifulSoup(f.read())

    streets = {}
    current = None

    def store():
        if current:
            current['previous'] = parse_previous(current['previous'])
            streets[current['name']] = current

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
            store()
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
    store()

    # Manual fixes
    #
    # The following changes are manual fixes for errors in the data or for
    # special cases that are too rare to be worth being implemented.
    streets['Albring']['previous'] = [(None, 'Albtalstraße'), (1935, 'Kolpingstraße')]
    streets['Am Alten Bahnhof']['previous'] = [(1920, 'Bahnhofplatz/Eisenbahnstraße')]
    streets['Am Illwig']['previous'] = [(1957,'Geranienstraße')]
    streets['Badenwerkstraße']['previous'] = [(None, 'Am Festplatz'), (1964, 'Lammstraße')]
    streets['Blumentorstraße']['previous'] = [(None, 'Blumenvorstadt'), (1905, 'Blumenstraße')]
    streets['Eichelgasse']['previous'] = [(1447, 'Müllers-/Eichelgäßle'), (None, 'Mühlgasse'), (1930, 'Mühlstraße')]
    streets['Fasanenplatz']['previous'] = [(1840, 'Fasanenstraße')]
    streets['Freydorfstraße']['previous'] = [(None, 'Grenadierstraße')]
    streets['Gablonzer Straße']['previous'] = [(None, 'Glasweg')]
    streets['Henri-Arnaud-Straße']['previous'] = [(None, 'Schulstraße'), (None, 'Zum Vogelsang')]
    streets['Im Fischerweg']['previous'] = [(None, 's Schiefe Wegle')]
    streets['Karl-Friedrich-Straße']['previous'] = [(1718, 'Carlsgasse'), (1741, 'Bärengasse'), (1787, 'Schlossgasse'), (None, 'Schlossstraße')]
    streets['Marstallstraße']['previous'] = [(None, 'Schlossgasse'), (None, 'Schlossplatz'), (None, 'Schlossstraße')]
    streets['Moltkestraße']['previous'] = [(None, 'Mühlburger Allee')]
    streets['Ochsentorstraße']['previous'] =  [(1700, 'Große Rappengasse'), (None, 'Adlerstraße')]
    streets['Pfinztalstraße']['previous'] = [(None, 'Hauptstraße'), (1933, 'Adolf-Hitler-Straße')]
    streets['Rathausplatz']['previous'] = [(None, 'Niddaplatz')]
    streets['Reinhold-Frank-Straße']['previous'] = [(1795, 'Kriegsstraße'), (1878, 'Westendstraße'), (1943, 'Reinhard-Heydrich-Straße'), (1945, 'Westendstraße')]
    streets['Rhode-Island-Allee']['previous'] = [(1953, 'Rhode Island Avenue')]
    streets['Ritterstraße']['previous'] = [(1718, 'Alt-Dresen-Gasse'), (None, 'Graf Leiningensche Gasse'), (None, 'Rittergasse')]
    streets['Rollerstraße']['previous'] = [(None, 'Endtengaß'), (1905, 'Kirchstraße')]
    streets['Schlossplatz']['previous'] = [(None, 'Großer/Äußerer Zirkel')]
    streets['Zirkel']['previous'] = [(None, 'Kleiner/Innerer Zirkel')]
    streets['Zunftstraße']['previous'] = [(None, 'Kronengaß'), (None, 'Kronenstraße')]

    with codecs.open(JSON, 'w', encoding='utf8') as f:
        json.dump(streets, f, sort_keys=True, indent=4, separators=(',', ': '))

