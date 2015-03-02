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
Script to extract raw data from Karlsruhe street names PDF.

Takes ``strassennamen.pdf`` and outputs data into ``raw_data.json``.
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


FLAGS = re.UNICODE | re.IGNORECASE


def collapse_ws(s):
    """
    Collapse whitespace in a string.
    """
    return re.sub(r'\s+', ' ', s.strip(), FLAGS)


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
    m = re.match(r'([^\d,]+)\D*(\d\d\d\d)?', s, FLAGS)
    if not m:
        return (None, None)
    g = m.groups()
    street = g[0].strip()
    street = re.sub(r'\s*-\s*', '-', street, FLAGS)
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

    street = street.replace('Strasse', 'Straße')
    return (street, year)


def parse_previous(s):
    """
    Parse list of previous street names.
    """
    if not s.strip():
        return []
    entries = []
    parts = re.split(r'[,;./]', s, FLAGS)
    for part in parts:
        part = part.strip()
        m = re.match(r'(?:bzw\.\s*)?(?:ca\.\s*)?(?:um\s*)?(\d\d\d\d?)\s+(.*)',
                     part, FLAGS)
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
            'year': year,
            'previous': parse_previous(entry['previous']),
            'info': entry['info'],
        }
    return streets


if __name__ == '__main__':
    HERE = os.path.dirname(os.path.abspath(__file__))
    PDF = os.path.join(HERE, 'strassennamen.pdf')
    JSON = os.path.join(HERE, 'raw_data.json')
    entries = extract_entries(PDF)
    streets = parse_entries(entries)

    def copy_props(src, dest, props=None):
        src_dict = streets[src]
        dest_dict = streets.setdefault(dest, {'previous':[], 'year':None})
        if not props:
            props = [k for k in src_dict if not k in ['previous', 'year']]
        for k in props:
            dest_dict[k] = src_dict[k]

    # Manual fixes and additions
    #
    # The following changes are manual fixes for errors in the data, fixes
    # for special cases that are too rare to be worth being implemented,
    # and manual additions for missing data.
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
    streets['Am Schloss Gottesaue'] = streets.pop('Am Schloß Gottesau')
    copy_props('Gottesauer Straße', 'Am Schloss Gottesaue')
    copy_props('Gottesauer Straße', 'Gottesauer Platz')
    streets['Englerstraße']['previous'] = [(1878, 'Schulstraße')]
    streets['Im Zeitvogel']['previous'] = [(1567, 'ackher am Zeytvogel')]
    streets['Gerda-Krüger-Nieland-Straße'] = streets.pop('Gerda-Krüger-Nieland')
    copy_props('Tullaweg', 'Tullastraße')
    copy_props('Tullaweg', 'Tullaplatz')
    streets['Gritznerstraße']['previous'] = [(1758, 'Aan der kleinen salzgaß'), (1906, 'Bahnhofstraße')]
    copy_props('Weinbrennerstraße', 'Weinbrennerplatz')
    streets['Douglasstraße']['previous'] = [(1837, 'Kasernenstraße')]
    streets['Mendelssohnplatz']['previous'] = [(1897, 'Mendelssohnplatz'), (1935, 'Rüppurrer-Tor-Platz')]
    copy_props('Martin-Luther-Straße', 'Martin-Luther-Platz')
    streets['Grazer Straße']['previous'] = [(1925, 'Wilhelmstraße'), (1936, 'Saarstraße')]
    copy_props('Baumeisterstraße', 'Reinhard-Baumeister-Platz')
    streets['Gustav-Meerwein-Straße']['previous'] = [(None, 'Walter-Tron-Straße')]
    streets['Turnerstraße']['previous'] = [(None, 'Jahnstraße')]
    streets['Riedstraße']['previous'] = [(1740, 'in denen Riethwiesen')]
    copy_props('Friedrichsplatz', 'Alte Friedrichstraße')
    streets['Haid-und-Neu-Straße']['previous'] = [(None, 'Karl-Wilhelm-Straße')]
    copy_props('Karl-Wilhelm-Straße', 'Karl-Wilhelm-Platz')
    copy_props('Fritz-Haber-Straße', 'Fritz-Haber-Weg')
    copy_props('Hildastraße', 'Nördliche Hildapromenade')
    copy_props('Hildastraße', 'Südliche Hildapromenade')
    streets['Ernst-Friedrich-Straße']['previous'] = [(1906, 'Friedrichstraße')]
    copy_props('Werderstraße', 'Werderplatz')
    copy_props('Stephanstraße', 'Stephanplatz')
    streets['Huttenstraße']['previous'] = [(None,'Schillerstraße'), (None, 'Neue Straße')]
    streets['Lützowstraße'] = streets.pop('Lützowplatz Lützowstraße')
    copy_props('Lützowstraße', 'Lützowplatz')
    copy_props('Brahmsstraße', 'Brahmsplatz')
    copy_props('Hermann-Löns-Weg', 'Lönsstraße')
    streets['Buschweg']['previous'] = [(1740, 'Acker am Busch')]
    streets['Gebhardstraße']['previous'] = [(None, 'Friedrichstraße')]
    streets['Sankt-Barbara-Weg']['previous'] = [(1936, 'Funkerweg')]
    copy_props('Ebersteinstraße', 'Graf-Eberstein-Straße')
    streets['Im Brunnenfeld']['previous'] = [(1963, 'Gartenstraße')]
    streets['Weiherfeldstraße']['previous'] = [(None, 'Eisenbahnstraße'), (1907, 'Weiherweg'), (1911, 'Weiherstraße')]
    streets['Henriette-Obermüller-Straße'] = streets.pop('Henriette_Obermüller-Straße')
    streets['Hotzerweg']['previous'] = [(1532, 'im Hozer'), (1714, 'im Hotzer')]
    copy_props('Goldgrundstraße', 'Goldwäschergasse')
    streets['Reickertstraße']['previous'] = [(1605, 'Reickler')]
    streets['Karolinenstraße']['previous'] = [(None, 'Augustastraße')]
    copy_props('Bismarckstraße', 'Kanzlerstraße')
    streets['Albert-Braun-Straße']['previous'] = [(1933, 'Danziger Straße')]
    copy_props('Allmendstraße', 'Zum Allmend')
    streets['Hauckstraße'] = streets.pop('Goethestraße')
    streets['Hauckstraße']['year'] = 1950
    streets['Goethestraße'] = {
        'year': 1878,
        'info': 'Johann Wolfgang von Goethe, + 28.8.1749 Frankfurt, + 22.3.1832 Weimar. Der Dichter hielt sich 1775, 1779 und 1815 in Karlsruhe auf. Während seines letzten Aufenthalts in Karlsruhe, als er im König von England, Ecke Kaiserstraße/Ritterstraße wohnte, traf er Johann Peter Hebel, Heinrich Jung-Stilling und Friedrich Weinbrenner. Faust.',
        'previous': [],
    }
    streets['Moningerstraße']['previous'] = [(1883, 'Grenzestraße')]
    streets['Froschhöhle'] = streets.pop('Froschhöhl')
    streets['Gewann Oberroßweide'] = streets.pop('Oberrossweide')
    streets['ESSO-Straße'] = streets.pop('Essostraße')
    streets['Stieglitzweg'] = streets.pop('Stieglitzstraße')
    streets['Ohiostraße'] = streets.pop('Ohio Straße')
    streets['Gotthard-Franz-Straße'] = streets.pop('Gotthart-Franz-Straße')
    streets['Wachhausstraße'] = streets.pop('Wachhaustraße')
    streets['Ohiostraße'] = streets.pop('Ohio Street')
    streets['Ringelberghohl'] = streets.pop('Ringelberghoh')
    streets['Däumlingweg'] = streets.pop('Däumlingsweg')
    streets['Bruchwaldstraße'] = streets.pop('Bruchwaldstaße')
    streets['Platz der Grundrechte'] = streets.pop('Platz der Gerechtigkeit')
    streets['Gerhard-Leibholz-Straße'] = streets.pop('Gebhard-Leibholz-Straße')
    streets['Gebhard-Müller-Straße'] = streets.pop('Gehard-Müller-Straße')
    streets['Schmetterlingweg'] = streets.pop('Schmetterlingsweg')
    streets['Otto-Ammann-Platz'] = streets.pop('Otto-Amman-Platz')

    # TODO: Information that's currently missing (does not include
    # most stuff that's already set to ``None``):
    #
    # - Who is Carl-Schäfer-Straße named for?
    # - What's the full name of Tannhäuser?
    # - Who is Stephanplatz named for?
    # - Who is Heinrich-Köhler-Platz named for?
    # - Who is Julius-Hirsch-Straße named for?
    # - When was Kaiserpassage renamed to its old name from Passage?
    # - Is Gutenbergplatz named for Johannes Gensfleich (like Gutenbergstraße)?
    # - Who is Gottfried-Fuchs-Platz named for?
    # - Who is Gustav-Meerwein-Straße named for?
    # - Who is Rolandstraße named for?
    # - Who is Leopoldplatz named for?
    # - Is Scheffelplatz named for Josef Victor von Scheffel (like Scheffelstraße)?
    # - Is Lameyplatz named for August Lamey (like Lameystraße)?
    # - Who is Robert-Sinner-Platz named for?
    # - Who is Gotthold-Mayer-Platz named for?
    # - Is Charlottenplatz named for Anna Charlotte Amalie (like Charlottenstraße)?
    # - Who is Otto-Dullenkopf-Park named for?
    # - "Platz am Wasserturm" is called Hanne-Landgraf-Platz since 2014 (named
    #   after Hanne Landgraf, https://de.wikipedia.org/wiki/Hanne_Landgraf)

    with codecs.open(JSON, 'w', encoding='utf8') as f:
        json.dump(streets, f, sort_keys=True, indent=4, separators=(',', ': '))
