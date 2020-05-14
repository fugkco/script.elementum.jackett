# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'resources', 'libs'))
sys.path.insert(0, os.path.dirname(__file__) + "/src")

from jackett import search
from elementum.provider import register, log

register(
    lambda x: search(x),
    lambda x: search(x, 'movie'),
    lambda x: search(x, 'episode'),
    lambda x: search(x, 'episode')
)
