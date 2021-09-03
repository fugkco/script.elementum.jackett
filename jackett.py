# -*- coding: utf-8 -*-
import os
import sys

from kodi_six import xbmcgui
from elementum.provider import register, log

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'resources', 'libs'))
sys.path.insert(0, os.path.dirname(__file__))

if __name__ == '__main__':
    import src.debugger as debugger
    import src.utils as utils
    import src.jackett as jackett

    if len(sys.argv) == 1:
        log.error("Elementum Jackett plugin must be run through Elementum")
        p_dialog = xbmcgui.Dialog()
        try:
            p_dialog.ok('Elementum [COLOR FFFF6B00]Jackett[/COLOR]', utils.translation(32800))
        finally:
            del p_dialog

        sys.exit(1)

    if sys.argv[1] == "validate_settings":
        jackett.validate_client()
    else:
        debugger.load()
        register(
            lambda q: jackett.search(q),
            lambda q: jackett.search(q, 'movie'),
            lambda q: jackett.search(q, 'episode'),
            lambda q: jackett.search(q, 'season'),
        )
