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



# Some examples dates from the data
# =================================
#
# Birth dates
# ===========
# "* 1122"
# "* um 1480"
# "geb. 10.11.1810"
# "* 3o.9.1859"
#
# Death dates
# ===========
# "† 19.4.1967"
# "+ 4.6.1875"
# "gest. 02.05.1899"
# "hingerichtet: 02.02.1945"
# "gestorben 29.02.1980"
# "+ Januar 1944"
# "+ vermutlich am 9.7.1386"
#
# Special cases
# =============
# "+19.3.1884 Eppingen, + 12.4.1971 Eppingen"
# "* 3o.9.1859"
# "1843-1906"


MONTHS = '(?:Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)'

DATE_REGEXES = [
    # "23.10.1805", "4.9.1965", "24.12. 1930"
    r'(?:am\s+)?\d\d?\.\s*\d\d?\.\s*(\d\d\d\d?)',

    # "10. Dezember 1815"
    r'(?:am\s+)?\d\d?\.\s*' + MONTHS + r'\s*(\d\d\d\d?)',

    # "1122", "um 1480"
    r'(?:um)?\s*(\d\d\d\d?)',

    # "Januar 1944"
    MONTHS + r'\s*(\d\d\d\d?)',
]

# Allow 'o' as a digit
DATE_REGEXES = [r.replace(r'\d', r'(?:\d|o)') for r in DATE_REGEXES]


def extract_year(s, prefixes=None):
    """
    Try to extract a year from a string.

    ``s`` is the string to search in. ``prefixes`` is an optional list
    of patterns that may occur before the actual date.

    Dates must match one of the regexes in ``DATE_REGEXES`` (in
    combination with one of the prefixes if any are given).

    The year of the first date found is returned. If no matching date
    is found then ``None`` is returned.
    """
    prefixes = [unicode(p) for p in (prefixes or [''])]
    for pattern in DATE_REGEXES:
        for prefix in prefixes:
            p = prefix + r'\s*' + pattern
            m = re.search(p, s, FLAGS)
            if not m:
                continue
            return int(m.groups()[0].replace('o', '0'))


def extract_person_data(info):
    """
    Try to extract person data from info text.

    Returns a tuple containing the person's name and the years of birth
    and death. Each of these may be ``None`` if the extraction failed.
    """
    birth = extract_year(info, prefixes=[r'\*', r'geb\.'])
    death = extract_year(info, prefixes=[r'†', r'\+', r'gest\.', r'hingerichtet:',
                         r'gestorben'])
    name = None
    if birth or death:
        m = re.match(r'^([\w\s\-.]+)', info, FLAGS)
        if m:
            name = m.groups()[0].strip()
            if name.endswith(' geb'):
                # Birth name ("geboren")
                name = name[:-4]
            elif name.endswith(' gen'):
                # Nick name ("genannt")
                name = name[:-4]
            elif name.endswith('.'):
                if not name[-2] in 'IVX':
                    # Not a roman literal
                    name = name[:-1]
    return name, birth, death


def parse_entries(entries):
    """
    Parse entries into street data.
    """
    streets = {}
    for entry in entries:
        name, year = parse_header(entry['header'])
        d = {
            'year': year,
            'previous': parse_previous(entry['previous']),
            'info': entry['info'],
        }
        person, birth, death = extract_person_data(entry['info'])
        if person or birth or death:
            d['person'] = person
            d['birth'] = birth
            d['death'] = death
        streets[name] = d
    return streets


if __name__ == '__main__':
    HERE = os.path.dirname(os.path.abspath(__file__))
    PDF = os.path.join(HERE, 'strassennamen.pdf')
    JSON = os.path.join(HERE, 'streetnames.json')
    entries = extract_entries(PDF)
    streets = parse_entries(entries)

    def copy_props(src, dest, props=None):
        src_dict = streets[src]
        dest_dict = streets.setdefault(dest, {'previous':[], 'year':None})
        if not props:
            props = [k for k in src_dict if not k in ['previous', 'year']]
        for k in props:
            dest_dict[k] = src_dict[k]

    def copy_person(src, dest):
        copy_props(src, dest, ['birth', 'death', 'person'])

    def a_person(name, person, birth, death):
        streets[name]['person'] = person
        streets[name]['birth'] = birth
        streets[name]['death'] = death

    def not_a_person(name):
        del streets[name]['person']
        del streets[name]['birth']
        del streets[name]['death']

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
    streets['Englerstraße']['person'] = 'Karl Engler'
    a_person('Guntherstraße', 'Gundahar', None, 436)
    streets['Agathenstraße']['person'] = 'Agathe von Baden-Durlach'
    streets['Im Zeitvogel']['previous'] = [(1567, 'ackher am Zeytvogel')]
    streets['Gerda-Krüger-Nieland-Straße'] = streets.pop('Gerda-Krüger-Nieland')
    streets['Gerda-Krüger-Nieland-Straße']['person'] = 'Gerda Krüger-Nieland'
    copy_props('Tullaweg', 'Tullastraße')
    copy_props('Tullaweg', 'Tullaplatz')
    a_person('Petrus-Waldus-Straße', 'Petrus Waldus', None, None)
    a_person('Am Thomashäusle', 'Thomas Dorner', None, None)
    streets['Gritznerstraße']['person'] = 'Max Karl Gritzner'
    streets['Gritznerstraße']['previous'] = [(1758, 'Aan der kleinen salzgaß'), (1906, 'Bahnhofstraße')]
    copy_props('Weinbrennerstraße', 'Weinbrennerplatz')
    streets['Martinstraße']['person'] = 'Sankt Martin'
    streets['Douglasstraße']['previous'] = [(1837, 'Kasernenstraße')]
    streets['Nikolausstraße']['person'] = 'Sankt Nikolaus'
    streets['Kaiserstraße']['person'] = 'Wilhelm I.'
    copy_person('Kaiserstraße', 'Kaiserpassage')
    copy_person('Kaiserstraße', 'Kaiserplatz')
    copy_person('Kaiserstraße', 'Kaiserallee')
    streets['Sepp-Herberger-Weg']['person'] = 'Joseph Herberger'
    streets['Mendelssohnplatz']['previous'] = [(1897, 'Mendelssohnplatz'), (1935, 'Rüppurrer-Tor-Platz')]
    streets['Mendelssohnplatz']['person'] = 'Moses Mendelssohn'
    copy_props('Martin-Luther-Straße', 'Martin-Luther-Platz')
    streets['Rolandplatz']['person'] = 'Roland'
    streets['Karlstraße']['person'] = 'Karl Ludwig Friedrich von Baden'
    not_a_person('Curjel-und-Moser-Straße')
    streets['Grazer Straße']['previous'] = [(1925, 'Wilhelmstraße'), (1936, 'Saarstraße')]
    copy_props('Baumeisterstraße', 'Reinhard-Baumeister-Platz')
    streets['Laurentiusstraße']['person'] = 'Sankt Laurentius'
    not_a_person('Winkler-Dentz-Straße')
    not_a_person('Eichrodtweg')
    not_a_person('Bernhardstraße')
    a_person('Bernhardusplatz', 'Bernhard II. von Baden', 1428, 1458)
    streets['Gustav-Meerwein-Straße']['previous'] = [(None, 'Walter-Tron-Straße')]
    not_a_person('Geschwister-Scholl-Straße')
    streets['Jakob-Dörr-Straße']['birth'] = 1884
    streets['Jakob-Dörr-Straße']['death'] = 1971
    streets['Turnerstraße']['previous'] = [(None, 'Jahnstraße')]
    a_person('Besoldgasse', 'Christoph Besold', None, None)
    streets['Ostendorfstraße']['death'] = 1915
    streets['Rudolfstraße']['person'] = 'Rudolf I. von Baden'
    not_a_person('Gebrüder-Bachert-Straße')
    streets['Riedstraße']['previous'] = [(1740, 'in denen Riethwiesen')]
    copy_props('Friedrichsplatz', 'Alte Friedrichstraße')
    streets['Haid-und-Neu-Straße']['previous'] = [(None, 'Karl-Wilhelm-Straße')]
    not_a_person('Haid-und-Neu-Straße')
    copy_props('Karl-Wilhelm-Straße', 'Karl-Wilhelm-Platz')
    copy_props('Fritz-Haber-Straße', 'Fritz-Haber-Weg')
    streets['Markusstraße']['person'] = 'Sankt Markus'
    streets['Luisenstraße']['person'] = 'Luise Marie Elisabeth von Preußen'
    copy_props('Hildastraße', 'Nördliche Hildapromenade')
    copy_props('Hildastraße', 'Südliche Hildapromenade')
    streets['Ernst-Friedrich-Straße']['previous'] = [(1906, 'Friedrichstraße')]
    streets['Ernst-Friedrich-Straße']['person'] = 'Ernst Friedrich'
    streets['Margarethenstraße']['person'] = 'Margarethe Margräfin von Baden'
    streets['Ludwig-Wilhelm-Straße']['persion'] = 'Ludwig Wilhelm Prinz von Baden'
    copy_props('Werderstraße', 'Werderplatz')
    streets['Ada-Lovelace-Straße']['person'] = 'Ada Lovelace'
    not_a_person('Bertholdstraße')
    streets['Karl-Friedrich-Straße']['person'] = 'Karl Friedrich von Baden'
    streets['Stephanstraße']['person'] = 'Heinrich von Stephan'
    copy_props('Stephanstraße', 'Stephanplatz')
    streets['Huttenstraße']['previous'] = [(None,'Schillerstraße'), (None, 'Neue Straße')]
    streets['Huttenstraße']['person'] = 'Ulrich Reichsritter von Hutten'
    a_person('Schultheiß-Kiefer-Straße','Erhard Kiefer', None, None)
    streets['Lützowstraße'] = streets.pop('Lützowplatz Lützowstraße')
    copy_props('Lützowstraße', 'Lützowplatz')
    streets['Sankt-Florian-Straße']['person'] = 'Sankt Florian'
    a_person('Blankenhornweg', 'Adolph Blankenhorn', 1843, 1906)
    copy_person('Karlstraße', 'Karlstor')
    copy_props('Brahmsstraße', 'Brahmsplatz')
    copy_props('Hermann-Löns-Weg', 'Lönsstraße')
    not_a_person('Gebrüder-Grimm-Straße')
    streets['Hubertusallee']['person'] = 'Hubrtus von Lüttich'
    streets['Buschweg']['previous'] = [(1740, 'Acker am Busch')]
    streets['Philippstraße']['person'] = 'Philipp I. von Baden'
    streets['Sankt-Valentin-Platz']['person'] = 'Sankt Valentin von Terni'
    streets['Gebhardstraße']['previous'] = [(None, 'Friedrichstraße')]
    streets['Gebhardstraße']['person'] = 'Gebhard III. von Zähringen'
    a_person('Rosalienberg', 'Rosalie Lichtenauer', None, None)
    streets['Charlottenstraße']['person'] = 'Anna Charlotte Amalie von Nassau-Dietz-Oranien'
    streets['Sankt-Barbara-Weg']['previous'] = [(1936, 'Funkerweg')]
    streets['Sankt-Barbara-Weg']['person'] = 'Sankt Barbara'
    copy_props('Ebersteinstraße', 'Graf-Eberstein-Straße')
    streets['Im Brunnenfeld']['previous'] = [(1963, 'Gartenstraße')]
    a_person('Graf-Konrad-Straße', 'Konrad I. von Kärnten', 975, 1011)
    streets['Weiherfeldstraße']['previous'] = [(None, 'Eisenbahnstraße'), (1907, 'Weiherweg'), (1911, 'Weiherstraße')]
    streets['Henriette-Obermüller-Straße'] = streets.pop('Henriette_Obermüller-Straße')
    streets['Hotzerweg']['previous'] = [(1532, 'im Hozer'), (1714, 'im Hotzer')]
    not_a_person('Christofstraße')
    streets['Hennebergstraße']['person'] = 'Berthold von Hohenberg'
    a_person('Winkelriedstraße', 'Arnold von Winkelried', None, 1386)
    copy_props('Goldgrundstraße', 'Goldwäschergasse')
    streets['Viktoriastraße']['person'] = 'Viktoria von Baden'
    streets['Reickertstraße']['previous'] = [(1605, 'Reickler')]
    a_person('Schultheißenstraße', 'Bernhard Metz', None, None)
    streets['Sophienstraße']['person'] = 'Sophie Wilhelmine von Schleswig-Holstein-Gottorf'
    streets['Augustastraße']['person'] = 'Augusta von Sachsen-Weimar-Eisenach'
    streets['Karolinenstraße']['previous'] = [(None, 'Augustastraße')]
    streets['Karolinenstraße']['person'] = 'Karoline von Baden'
    copy_props('Bismarckstraße', 'Kanzlerstraße')
    streets['Albert-Braun-Straße']['previous'] = [(1933, 'Danziger Straße')]
    not_a_person('Friedenstraße')
    copy_props('Allmendstraße', 'Zum Allmend')
    streets['Marie-Alexandra-Straße']['person'] = 'Marie Alexandra von Baden'
    streets['Erbprinzenstraße']['person'] = 'Karl Ludwig von Baden'
    streets['Hauckstraße'] = streets.pop('Goethestraße')
    streets['Hauckstraße']['year'] = 1950
    streets['Goethestraße'] = {
        'year': 1878,
        'info': 'Johann Wolfgang von Goethe, + 28.8.1749 Frankfurt, + 22.3.1832 Weimar. Der Dichter hielt sich 1775, 1779 und 1815 in Karlsruhe auf. Während seines letzten Aufenthalts in Karlsruhe, als er im König von England, Ecke Kaiserstraße/Ritterstraße wohnte, traf er Johann Peter Hebel, Heinrich Jung-Stilling und Friedrich Weinbrenner. Faust.',
        'birth': 1749,
        'death': 1832,
        'previous': [],
    }
    streets['Ernststraße']['person'] = 'Ernst I. von Baden-Durlach'

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

    # TODO: The following streets are named after several people. The current
    # data format cannot describe that properly:
    #
    #    Eichrodtweg
    #    Winkler-Dentz-Straße
    #    Curjel-und-Moser-Straße
    #    Bernhardstraße
    #    Geschwister-Scholl-Straße
    #    Gebrüder-Bachert-Straße
    #    Bertholdstraße
    #    Peter-und-Paul-Platz
    #    Engler-Bunte-Ring
    #    Gebrüder-Grimm-Straße
    #    Christofstraße

    with codecs.open(JSON, 'w', encoding='utf8') as f:
        json.dump(streets, f, sort_keys=True, indent=4, separators=(',', ': '))
