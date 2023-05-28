#!/usr/bin/env python3
import fileinput
import os

import sys
from os import path, pardir

from xml.dom.minidom import parse

root = path.abspath(path.join(path.dirname(path.abspath(__file__)), pardir))

if __name__ == '__main__':
    if len(sys.argv) != 4:
        app = sys.argv[0]
        print("usage: {} version version_date news_section".format(app))
        print("")
        print("example:")
        print('\t{} 0.1.2 "Something happened!"'.format(app))
        print('\techo "Something happened!" | {} 0.1.2 2022-12-30 -'.format(app))
        sys.exit(1)

    _, version, version_date, news = sys.argv
    if version[0:1] == 'v':
        version = version[1:]

    if news == "-" or os.path.isfile(news):
        news = "".join(list(fileinput.input(files=news)))

    news = f"[B]{version}[/B] ({version_date})\n\n{news.rstrip()}\n"

    doc = parse(path.join(root, 'addon.xml'))
    doc.getElementsByTagName("addon")[0].setAttribute('version', version)
    for el in doc.getElementsByTagName("extension"):
        if el.getAttribute("point") == "xbmc.addon.metadata":
            newsEl = doc.createElement("news")
            newsEl.appendChild(doc.createTextNode(news))
            el.appendChild(newsEl)
            break

    print(doc.toprettyxml(indent='  ', newl=''))
