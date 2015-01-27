#!/usr/bin/env python
# vim: set fileencoding=utf-8 :

"""
Script to extract text from Karlsruhe street names PDF.

Takes ``strassennamen.pdf`` and outputs its text into
``strassennamen.txt``.
"""

import codecs
import cStringIO
import os.path

from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.pdfpage import PDFPage
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams


def extract_text(pdf_filename, encoding='utf-8'):
    """
    Extract text from a PDF file.
    """
    output = cStringIO.StringIO()
    rsrcmgr = PDFResourceManager(caching=True)
    device = TextConverter(rsrcmgr, output, codec=encoding,
                           laparams=LAParams())
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
    return output.getvalue().decode('utf8')


if __name__ == '__main__':
    HERE = os.path.dirname(os.path.abspath(__file__))
    PDF = os.path.join(HERE, 'strassennamen.pdf')
    TXT = os.path.join(HERE, 'strassennamen.txt')
    with codecs.open(TXT, 'w', encoding='utf8') as f:
        f.write(extract_text(PDF))
