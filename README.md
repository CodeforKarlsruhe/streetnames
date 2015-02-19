Streetnames of Karlsruhe
========================
Background information on the street names in [Karlsruhe](https://en.wikipedia.org/wiki/Karlsruhe).

Inspired by [UlmApi](http://www.ulmapi.de)'s [Streetdudes](http://www.ulmapi.de/streetdudes/) project.


Developers
----------
The data extraction is done in Python. After cloning the repository, create a virtual environment
and activate it:

    $ virtualenv venv
    $ source venv/bin/activate

Install the necessary Python packages:

    $ pip install -r requirements.txt

If the installation of `lxml` fails you may need to install some additional
[development packages](https://stackoverflow.com/q/13019942/857390).

The data for this visualization comes from two sources: The background information on the street
names comes from
[a PDF provided by the City of Karlsruhe](http://www.karlsruhe.de/b3/bauen/tiefbau/strassenverkehr/strassennamenbuch.de).
The geographic data comes from [OpenStreetMap](http://www.openstreetmap.org).

For the OSM data conversion you need to have [Osmosis](http://wiki.openstreetmap.org/wiki/Osmosis) installed.

First extract the street name information from the PDF:

    $ data/extract_raw_data.py
    $ data/parse_raw_data.py

Then download the necessary OSM data (about 80M) and extract the coordinates:

    $ data/get_osm_data.sh
    $ data/extract_coordinates.py

Finally, merge the information from both sources into the file `web/streetnames.geojson` and create the
individual datasets:

    $ data/merge.py
    $ data/prepare_datasets.py

You can now open `web/index.html` in your browser.
