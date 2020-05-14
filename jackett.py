# -*- coding: utf-8 -*-
import os
import sys

from src import debugger

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'resources', 'libs'))
sys.path.insert(0, os.path.dirname(__file__))

from src.jackett import search
from elementum.provider import register, log


def search_movie(payload):
    return search(payload, 'movie')


def search_episode(payload):
    res = search(payload, 'episode')
    log.info("jackett - episode data={}".format(repr(res)))
    return res


def search_season(payload):
    return search(payload, 'season')


if __name__ == '__main__':
    debugger.load()
    register(search, search_movie, search_episode, search_season)
