import logging

from kodi_six import xbmc

import addon


class XBMCHandler(logging.StreamHandler):
    def __init__(self):
        logging.StreamHandler.__init__(self)
        formatter = logging.Formatter("[%(name)s] %(message)s")
        self.setFormatter(formatter)

    def emit(self, record):
        levels = {
            logging.CRITICAL: xbmc.LOGFATAL,
            logging.ERROR: xbmc.LOGERROR,
            logging.WARNING: xbmc.LOGWARNING,
            logging.INFO: xbmc.LOGINFO,
            logging.DEBUG: xbmc.LOGDEBUG,
            logging.NOTSET: xbmc.LOGNONE,
        }
        xbmc.log(self.format(record), levels[record.levelno])

    def flush(self):
        pass


log = logging.getLogger(addon.ID)
log.handlers = []

log.addHandler(XBMCHandler())

