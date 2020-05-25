# -*- coding: utf-8 -*-
import os
import sys

from elementum.provider import register

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'resources', 'libs'))
sys.path.insert(0, os.path.dirname(__file__))

if __name__ == '__main__':
    from src import debugger
    from src.jackett import search

    debugger.load()
    register(
        lambda q: search(q),
        lambda q: search(q, 'movie'),
        lambda q: search(q, 'episode'),
        lambda q: search(q, 'season'),
    )
