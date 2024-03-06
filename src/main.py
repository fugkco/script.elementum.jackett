# -*- coding: utf-8 -*-
from os import path

import sys
# Workaround for kodi RuntimeError https://kodi.wiki/view/Python_Problems#asyncio
sys.modules['_asyncio'] = None
import asyncio
from elementum.provider import register
from kodi_six import xbmcgui

from logger import log

sys.path.insert(0, path.realpath(path.join(path.dirname(__file__), '..', 'resources', 'libs')))
sys.path.insert(0, path.dirname(__file__))

# fix asyncio.run() on win
if sys.platform == "win32" and (3, 8, 0) <= sys.version_info < (3, 9, 0):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


if __name__ == '__main__':
    import debugger
    import utils
    import jackett

    if len(sys.argv) == 1:
        log.error("Elementum Jackett plugin must be run through Elementum")
        p_dialog = xbmcgui.Dialog()
        try:
            p_dialog.ok('Elementum [COLOR FFFF6B00]Jackett[/COLOR]', utils.translation(32800))
        finally:
            del p_dialog

        sys.exit(1)

    if sys.argv[1] == "validate_settings":
        asyncio.run(jackett.validate_client())
    else:
        debugger.load()
        register(
            lambda q: jackett.search(q),
            lambda q: jackett.search(q, 'movie'),
            lambda q: jackett.search(q, 'episode'),
            lambda q: jackett.search(q, 'season'),
        )
