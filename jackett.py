# -*- coding: utf-8 -*-
import os
import sys

import xbmcgui
from elementum.provider import register, log

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'resources', 'libs'))
sys.path.insert(0, os.path.dirname(__file__))

if __name__ == '__main__':
    from src import debugger, utils
    from src.jackett import search, validate_client

    if len(sys.argv) == 1:
        log.error("Elementum Jackett plugin must be run through Elementum")
        p_dialog = xbmcgui.Dialog()
        try:
            p_dialog.ok('Elementum [COLOR FFFF6B00]Jackett[/COLOR]', utils.translation(32800))
        finally:
            del p_dialog

        sys.exit(1)

    if sys.argv[1] == "validate_settings":
        validate_client()
    else:
        debugger.load()
        register(
            lambda q: search(q),
            lambda q: search(q, 'movie'),
            lambda q: search(q, 'episode'),
            lambda q: search(q, 'season'),
        )
