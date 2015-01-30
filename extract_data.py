#!/usr/bin/env python
# vim: set fileencoding=utf-8 :

"""
Script to extract data from Karlsruhe street names PDF.

Takes ``strassennamen.pdf`` and outputs data into ``streetnames.json``.
"""

from __future__ import unicode_literals

import codecs
import cStringIO
import json
import os.path
import re

from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.pdfpage import PDFPage
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams


def collapse_ws(s):
    """
    Collapse whitespace in a string.
    """
    return re.sub(r'\s+', ' ', s.strip())


# Strings that are part of the general header
HEADER_STRINGS = ['Liegenschaftsamt', 'Straßennamen in Karlsruhe']

class Converter(TextConverter):

    def __init__(self, *args, **kwargs):
        super(Converter, self).__init__(*args, **kwargs)
        self.entries = []
        self._entry = None

    def _store_entry(self):
        if self._entry:
            self._entry = {k: collapse_ws(v) for k, v in self._entry.items()}
            h = self._entry['header']
            if len(h) > 1 and h not in HEADER_STRINGS:
                self.entries.append(self._entry)
        self._entry = {'header': '', 'previous': '', 'info': ''}

    def render_string(self, textstate, seq):
        # We use the font style to distinguish entry headers, previous
        # street names and general information. Note that the italic
        # text in this PDF is not due to an italic font but is achieved
        # using a matrix transform.
        font = textstate.font
        chars = []
        for s in seq:
            if isinstance(s, str):
                chars.extend(font.to_unichr(char) for char in font.decode(s))
        text = ''.join(chars)
        if textstate.matrix[2] == 0:
            if textstate.font.basefont.endswith('Bd'):
                # Bold font
                self._store_entry()
                self._entry['header'] += text
            else:
                # Light font
                self._entry['info'] += text
        else:
            # Italic font
            self._entry['previous'] += text
        return super(Converter, self).render_string(textstate, seq)

    def close(self):
        self._store_entry()
        return super(Converter, self).close()


def extract_entries(pdf_filename):
    """
    Extract entries from PDF file.
    """
    output = cStringIO.StringIO()
    rsrcmgr = PDFResourceManager(caching=True)
    device = Converter(rsrcmgr, output, codec='utf8', laparams=LAParams())
    page_numbers = set()
    try:
        with open(pdf_filename, 'rb') as f:
            interpreter = PDFPageInterpreter(rsrcmgr, device)
            for page in PDFPage.get_pages(f, page_numbers, maxpages=0,
                                          password='', caching=True,
                                          check_extractable=True):
                interpreter.process_page(page)
    finally:
        device.close()
    return device.entries


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


def parse_entries(entries):
    """
    Parse entries into street data.
    """
    streets = {}
    for entry in entries:
        name, year = parse_header(entry['header'])
        streets[name] = {
            'previous': parse_previous(entry['previous']),
            'info': entry['info'],
        }
    return streets


if __name__ == '__main__':
    HERE = os.path.dirname(os.path.abspath(__file__))
    PDF = os.path.join(HERE, 'strassennamen.pdf')
    JSON = os.path.join(HERE, 'streetnames.json')
    entries = extract_entries(PDF)
    streets = parse_entries(entries)

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
