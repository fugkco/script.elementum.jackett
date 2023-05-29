import logging

from kodi_six import xbmc

import addon


class XBMCHandler(logging.StreamHandler):
    xbmc_levels = {
        'DEBUG': 0,
        'INFO': 2,
        'WARNING': 3,
        'ERROR': 4,
        'CRITICAL': 5,
    }

    def emit(self, record):
        xbmc_level = self.xbmc_levels.get(record.levelname)
        xbmc.log(self.format(record), xbmc_level)


log = logging.getLogger(addon.ID)

handler = XBMCHandler()
handler.setFormatter(logging.Formatter('[%(name)s] %(message)s'))
log.addHandler(handler)
