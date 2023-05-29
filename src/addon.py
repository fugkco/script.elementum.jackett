from kodi_six import xbmcaddon, xbmcvfs

ADDON = xbmcaddon.Addon()
ID = ADDON.getAddonInfo("id")
NAME = ADDON.getAddonInfo("name")
PATH = ADDON.getAddonInfo("path")
ICON = ADDON.getAddonInfo("icon")
PROFILE = ADDON.getAddonInfo("profile")
VERSION = ADDON.getAddonInfo("version")
HOME = xbmcvfs.translatePath("special://home/addons/")
TMP = xbmcvfs.translatePath("special://temp")
if not HOME:
    HOME = '..'
