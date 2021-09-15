#!/usr/bin/env python3
import sys
from os import path, pardir

from xml.dom.minidom import parse

root = path.abspath(path.join(path.dirname(path.abspath(__file__)), pardir))

pretty_print = lambda d: '\n'.join([line for line in d.toprettyxml(indent=' ' * 2).split('\n') if line.strip()])

if __name__ == '__main__':
    if len(sys.argv) != 2:
        app = sys.argv[0]
        print("usage: {} version".format(app))
        print("")
        print("example:")
        print("\t{} 0.1.2".format(app))
        sys.exit(1)

    version = sys.argv[1]
    if version[0:1] == 'v':
        version = version[1:]

    doc = parse(path.join(root, 'addon.xml'))
    doc.getElementsByTagName("addon")[0].setAttribute('version', version)
    print(pretty_print(doc))
