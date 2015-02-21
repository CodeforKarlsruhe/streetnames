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
Script to parse raw street name data and classify name topics.

Takes ``raw_data.json`` and outputs data into ``classification.json``.
"""

from __future__ import unicode_literals

import codecs
import collections
import json
import math
import os.path


# In brackets each topic's ID is given (e.g. "A" for "Art"). An entries
# topic is the concatenation of the hierarchical IDs, separated by
# slashes (e.g. "A/M" for "Art/Music").
#
# - [A]rt
#   - [L]iterature
#   - [M]usic
#   - [P]ainting
# - [E]conomy
#     - [C]ompany
# - [G]eography (something that has a lat/lon coordinates)
#   - [B]uilding
#   - [F]orest
#   - [L]ink (link between two places, e.g. a road or railroad)
#   - [M]ountain
#   - [R]iver
#   - [R]egion (countries, states, etc.)
#   - [S]ettlement (cities, villages, ...)
#   - [V]alley
#   - [W]ater (rivers, lakes, ...)
# - [H]umanities
#   - [H]istory
#   - [L]aw
#   - [P]ilosophy
# - [M]ilitary
# - [N]ature
#   - [A]nimal
#   - [P]lant
# - N[o]bility
# - [P]olitics (e.g. politician)
# - [R]eligion
# - [S]cience & Technology (e.g. scientists)
#   - [M]edicine
# - [T]ribe
#
# TODO:
#
#   - "Religion" is orthogonal to many other things (e.g. a church is
#     both religious and a building)
#
#   - What to do with tribes like Germanen, Alemannen, Franken, etc.?
#
#   - What to with the Adel?
#
#   - There are many names that relate to farming (often orhogonal to
#     geographic)
#
#   - Should we distinguish between geographic names that relate to
#     things at the specific street (e.g. "Hinter den Scheunen") and
#     those that relate to things somewhere else (e.g. "Reutlinger
#     Straße")?
#
#   - A separate category for crafts (e.g. "Schuster")?


def _normalize(word):
    return unicode(word).lower()


_KEYWORDS = collections.defaultdict(lambda: [])

def _add_kws(id, words):
    id = tuple(id.split('/'))
    _KEYWORDS[id].extend(_normalize(w) for w in words.split())

_add_kws('A', 'kunst keramik')
_add_kws('A/L', 'dicht schriftsteller zwerg märchen sage epos mytho')
_add_kws('A/M', 'musik komponist lyrik lied')
_add_kws('A/P', 'maler zeichner')
_add_kws('E', 'volkswirt hansa hanse schiffer krämer industrie zoll')
_add_kws('E/C', """firma brauerei unternehm gmbh co kg ag raffinerie druckerei
         verlag""")
_add_kws('G', 'lage hafen friedhof flur park gewann fels insel äcker')
_add_kws('G/B', """haus gaststätte gastwirtschaft bahnhof bad garten gärten
         erbaut schloss schule burg baut wiese weide kirche kloster postamt
         mühle ziegelei""")
_add_kws('G/F', 'wald wäldle')
_add_kws('G/L', 'straße verbindung weg strecke pfad')
_add_kws('G/M', 'berg gebirg erhebung')
_add_kws('G/R', 'heimat landschaft bundesstaat bundesland provinz')
_add_kws('G/S', 'stadt siedlung dorf ort gemeinde')
_add_kws('G/W', """fluss fluß bach see entspringt mündet kanal graben quell
         brunnen""")
_add_kws('H/H', 'histori')
_add_kws('H/L', 'jurist gericht anwalt kanzlei')
_add_kws('H/P', 'philosoph')
_add_kws('M', """feldzug militär soldat krieg kämpfer kampf regiment
         bataillon schlacht general""")
_add_kws('N/P', """gehölz blume pflanze strauch kraut getreide frucht staude
         obst baum bäume""")
_add_kws('N/A', 'insekt vogel falter schmetterling marder fisch')
_add_kws('O', 'geschlecht')
_add_kws('P', """politi präsident bundeskanzler abgeordneter stadtrat
         minister reichstag bürgermeister bundestag sozialis schultheiß""")
_add_kws('R', 'pater theolog bischof priester heilig religi apostel gott')
_add_kws('S', """mathematik physik maschinenbau geograph forsch konstru
         ingenieur erfind""")
_add_kws('S/M', 'medizin arzt pflege krank psychia pharma')
_add_kws('T', 'stamm')


_NUM_CHILDREN = collections.defaultdict(lambda: 0)
for id in _KEYWORDS:
    if len(id) > 1:
        _NUM_CHILDREN[id[:-1]] += 1


# We perform hierarchical classification. This means that we try
# to find for each street name the topic which is as specific as
# possible while being a good enough match. For example, something
# should only be classified as "Art" if none of the "Art"-subtopics
# matches well enough but "Art" does.
#
# For this we first match each name against each individual topic. We
# then prune that score tree from the leaves upwards: If a leaf topic
# hasn't enough points we add them to its parent. Once every leaf node
# has enough points we take the one with the most points.


def calculate_inverse_document_frequencies(terms, docs):
    """
    Calculate inverse document frequencies of a set of documents.
    """
    idfs = {}
    normalized_docs = [_normalize(doc) for doc in docs]
    for term in terms:
        term = _normalize(term)
        n = sum(1 for doc in normalized_docs if term in doc)
        if not n:
            raise ValueError(term)
        idfs[term] = 1.0 / n
    return idfs


_MIN_SCORE = 1  # Minimal leaf score (leaf nodes with less are trimmed)


def _s(id):
    return '/'.join(id)


def classify(text, idfs):
    """
    Classify a text.

    Returns a list of tuples containing the classification candidates
    of the text (with decreasing scores). Each tuple contains a
    classification string and its score.
    """
    # Score each individual topic
    info = [_normalize(w) for w in text.split()]
    scores = collections.defaultdict(lambda: 0)
    for id, keywords in _KEYWORDS.iteritems():
        for keyword in keywords:
            term_frequency = sum(1 for word in info if keyword in word)
            if term_frequency > 0:
                tfidf = term_frequency * idfs[keyword]
                #print keyword.encode('utf8'), term_frequency, tfidf
                scores[id] += tfidf
        if scores[id]:
            scores[id] = 1 + math.log(1 + scores[id])

    if not scores:
        return []

    #print

    #for id in sorted(scores):
    #    if scores[id] > 0:
    #        print _s(id), scores[id]

    # Prune leaves
    depth = max(len(id) for id in scores) + 1
    while depth > 1:
        depth -= 1
        items = scores.items()  # Copy because we modify the dict
        for id, score in items:
            if len(id) != depth:
                # Not a leaf node
                continue
            if score < _MIN_SCORE:
                if score > 0:
                    if depth > 1:
                        parent = id[:-1]
                        #print "Adding score of", _s(id), "to that of", _s(parent)
                        scores[parent] += score / _NUM_CHILDREN[parent]
                    #print "Trimming %s (%f)" % (_s(id), score)
                del scores[id]

    return sorted(scores.items(), key=lambda i: i[1])


if __name__ == '__main__':
    HERE = os.path.dirname(os.path.abspath(__file__))
    SOURCE = os.path.join(HERE, 'raw_data.json')
    TARGET = os.path.join(HERE, 'classification.json')

    with codecs.open(SOURCE, 'r', encoding='utf8') as f:
        streets = json.load(f)

    all_keywords = [w for words in _KEYWORDS.itervalues() for w in words]
    all_infos = (s['info'] for s in streets.itervalues())
    idfs = calculate_inverse_document_frequencies(all_keywords, all_infos)

    classification = {}
    for name, props in streets.iteritems():
        classes = classify(props['info'], idfs)
        if classes:
            cls = classes[0][0]
        else:
            cls = None
        classification[name] = cls

    for name in sorted(classification):
        if not classification[name]:
            print ('No classification for "%s"' % name).encode('utf8')

    with codecs.open(TARGET, 'w', encoding='utf8') as f:
        json.dump(classification, f, sort_keys=True, indent=4, separators=(',', ': '))
