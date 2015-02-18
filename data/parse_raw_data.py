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
Script to parse raw street name data and extract secondary information.

Takes ``raw_data.json`` and outputs data into ``names.json``.
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


def parse_entries(streets):
    """
    Parse street name data to extract additional information.
    """
    for street in streets.itervalues():
        person, birth, death = extract_person_data(street['info'])
        if person or birth or death:
            street['person'] = person
            street['birth'] = birth
            street['death'] = death


if __name__ == '__main__':
    HERE = os.path.dirname(os.path.abspath(__file__))
    SOURCE = os.path.join(HERE, 'raw_data.json')
    TARGET = os.path.join(HERE, 'names.json')

    with codecs.open(SOURCE, 'r', encoding='utf8') as f:
        streets = json.load(f)

    parse_entries(streets)

    def copy_person(src, dest):
        src_dict = streets[src]
        dest_dict = streets[dest]
        for k in ['birth', 'death', 'person']:
            dest_dict[k] = src_dict[k]

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
    streets['Englerstraße']['person'] = 'Karl Engler'
    a_person('Guntherstraße', 'Gundahar', None, 436)
    streets['Agathenstraße']['person'] = 'Agathe von Baden-Durlach'
    streets['Gerda-Krüger-Nieland-Straße']['person'] = 'Gerda Krüger-Nieland'
    copy_person('Tullaweg', 'Tullastraße')
    copy_person('Tullaweg', 'Tullaplatz')
    a_person('Petrus-Waldus-Straße', 'Petrus Waldus', None, None)
    a_person('Am Thomashäusle', 'Thomas Dorner', None, None)
    streets['Gritznerstraße']['person'] = 'Max Karl Gritzner'
    copy_person('Weinbrennerstraße', 'Weinbrennerplatz')
    streets['Martinstraße']['person'] = 'Sankt Martin'
    streets['Nikolausstraße']['person'] = 'Sankt Nikolaus'
    streets['Kaiserstraße']['person'] = 'Wilhelm I.'
    copy_person('Kaiserstraße', 'Kaiserpassage')
    copy_person('Kaiserstraße', 'Kaiserplatz')
    copy_person('Kaiserstraße', 'Kaiserallee')
    streets['Sepp-Herberger-Weg']['person'] = 'Joseph Herberger'
    streets['Mendelssohnplatz']['person'] = 'Moses Mendelssohn'
    copy_person('Martin-Luther-Straße', 'Martin-Luther-Platz')
    streets['Rolandplatz']['person'] = 'Roland'
    streets['Karlstraße']['person'] = 'Karl Ludwig Friedrich von Baden'
    not_a_person('Curjel-und-Moser-Straße')
    copy_person('Baumeisterstraße', 'Reinhard-Baumeister-Platz')
    streets['Laurentiusstraße']['person'] = 'Sankt Laurentius'
    not_a_person('Winkler-Dentz-Straße')
    not_a_person('Eichrodtweg')
    not_a_person('Bernhardstraße')
    a_person('Bernhardusplatz', 'Bernhard II. von Baden', 1428, 1458)
    not_a_person('Geschwister-Scholl-Straße')
    streets['Jakob-Dörr-Straße']['birth'] = 1884
    streets['Jakob-Dörr-Straße']['death'] = 1971
    a_person('Besoldgasse', 'Christoph Besold', None, None)
    streets['Ostendorfstraße']['death'] = 1915
    streets['Rudolfstraße']['person'] = 'Rudolf I. von Baden'
    not_a_person('Gebrüder-Bachert-Straße')
    copy_person('Friedrichsplatz', 'Alte Friedrichstraße')
    not_a_person('Haid-und-Neu-Straße')
    copy_person('Karl-Wilhelm-Straße', 'Karl-Wilhelm-Platz')
    copy_person('Fritz-Haber-Straße', 'Fritz-Haber-Weg')
    streets['Markusstraße']['person'] = 'Sankt Markus'
    streets['Luisenstraße']['person'] = 'Luise Marie Elisabeth von Preußen'
    copy_person('Hildastraße', 'Nördliche Hildapromenade')
    copy_person('Hildastraße', 'Südliche Hildapromenade')
    streets['Ernst-Friedrich-Straße']['person'] = 'Ernst Friedrich'
    streets['Margarethenstraße']['person'] = 'Margarethe Margräfin von Baden'
    streets['Ludwig-Wilhelm-Straße']['person'] = 'Ludwig Wilhelm Prinz von Baden'
    copy_person('Werderstraße', 'Werderplatz')
    streets['Ada-Lovelace-Straße']['person'] = 'Ada Lovelace'
    not_a_person('Bertholdstraße')
    streets['Karl-Friedrich-Straße']['person'] = 'Karl Friedrich von Baden'
    streets['Stephanstraße']['person'] = 'Heinrich von Stephan'
    copy_person('Stephanstraße', 'Stephanplatz')
    streets['Huttenstraße']['person'] = 'Ulrich Reichsritter von Hutten'
    a_person('Schultheiß-Kiefer-Straße','Erhard Kiefer', None, None)
    copy_person('Lützowstraße', 'Lützowplatz')
    streets['Sankt-Florian-Straße']['person'] = 'Sankt Florian'
    a_person('Blankenhornweg', 'Adolph Blankenhorn', 1843, 1906)
    copy_person('Karlstraße', 'Karlstor')
    copy_person('Brahmsstraße', 'Brahmsplatz')
    copy_person('Hermann-Löns-Weg', 'Lönsstraße')
    not_a_person('Gebrüder-Grimm-Straße')
    streets['Hubertusallee']['person'] = 'Hubrtus von Lüttich'
    streets['Philippstraße']['person'] = 'Philipp I. von Baden'
    streets['Sankt-Valentin-Platz']['person'] = 'Sankt Valentin von Terni'
    streets['Gebhardstraße']['person'] = 'Gebhard III. von Zähringen'
    a_person('Rosalienberg', 'Rosalie Lichtenauer', None, None)
    streets['Charlottenstraße']['person'] = 'Anna Charlotte Amalie von Nassau-Dietz-Oranien'
    streets['Sankt-Barbara-Weg']['person'] = 'Sankt Barbara'
    a_person('Graf-Konrad-Straße', 'Konrad I. von Kärnten', 975, 1011)
    not_a_person('Christofstraße')
    streets['Hennebergstraße']['person'] = 'Berthold von Hohenberg'
    a_person('Winkelriedstraße', 'Arnold von Winkelried', None, 1386)
    streets['Viktoriastraße']['person'] = 'Viktoria von Baden'
    a_person('Schultheißenstraße', 'Bernhard Metz', None, None)
    streets['Sophienstraße']['person'] = 'Sophie Wilhelmine von Schleswig-Holstein-Gottorf'
    streets['Augustastraße']['person'] = 'Augusta von Sachsen-Weimar-Eisenach'
    streets['Karolinenstraße']['person'] = 'Karoline von Baden'
    copy_person('Bismarckstraße', 'Kanzlerstraße')
    not_a_person('Friedenstraße')
    streets['Marie-Alexandra-Straße']['person'] = 'Marie Alexandra von Baden'
    streets['Erbprinzenstraße']['person'] = 'Karl Ludwig von Baden'
    streets['Hauckstraße']['year'] = 1950
    streets['Goethestraße'].update({
        'person': 'Johann Wolfgang von Goethe',
        'birth': 1749,
        'death': 1832,
    })
    streets['Ernststraße']['person'] = 'Ernst I. von Baden-Durlach'

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

    with codecs.open(TARGET, 'w', encoding='utf8') as f:
        json.dump(streets, f, sort_keys=True, indent=4, separators=(',', ': '))
