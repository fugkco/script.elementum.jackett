# coding=utf-8
import os
import re
from collections import OrderedDict

import xbmc
import xbmcaddon
import xbmcgui
from elementum.provider import log

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo("id")
ADDON_NAME = ADDON.getAddonInfo("name")
ADDON_PATH = ADDON.getAddonInfo("path").decode('utf-8')
ADDON_ICON = ADDON.getAddonInfo("icon").decode('utf-8')
ADDON_PROFILE = ADDON.getAddonInfo("profile")
ADDON_VERSION = ADDON.getAddonInfo("version")
PATH_ADDONS = xbmc.translatePath("special://home/addons/")
PATH_TEMP = xbmc.translatePath("special://temp")
if not ADDON_PATH:
    ADDON_PATH = '..'

resolutions = OrderedDict([
    ('240p', [r'240[p]', r'vhs\-?rip']),
    ('480p', [r'480[p]', r'xvid', r'dvd', r'dvdrip', r'hdtv', r'web\-(dl)?rip', r'iptv', r'sat\-?rip',
              r'tv\-?rip']),
    ('720p', [r'720[p]', r'1280x720', r'hd720p?', r'hd\-?rip', r'b[rd]rip']),
    ('1080p', [r'1080[ip]', r'1920x1080', r'hd1080p?', r'fullhd', r'fhd', r'blu\W*ray', r'bd\W*remux']),
    ('2k', [r'1440[p]', r'2k']),
    ('4k', [r'4k', r'2160[p]', r'uhd', r'4k', r'hd4k']),
])

_release_types = OrderedDict([
    ('brrip', [r'brrip', r'bd\-?rip', r'blu\-?ray', r'bd\-?remux']),
    ('webdl', [r'web', r'web_?\-?dl', r'web\-?rip', r'dl\-?rip', r'yts']),
    ('hdrip', [r'hd\-?rip']),
    ('hdtv', [r'hd\-?tv']),
    ('dvd', [r'dvd', r'dvd\-?rip', r'vcd\-?rip', r'divx', r'xvid']),
    ('dvdscr', [r'dvd\-?scr(eener)?']),
    ('screener', [r'screener', r'scr']),
    ('3d', [r'3d']),
    ('telesync', [r'telesync', r'ts', r'tc']),
    ('cam', [r'cam(\-rip)?', r'hd\-?cam']),
    ('tvrip', [r'tv\-?rip', r'sat\-?rip', r'dvb']),
    ('vhsrip', [r'vhs\-?rip']),
    ('iptvrip', [r'iptv\-?rip']),
    ('trailer', [r'trailer']),
    ('workprint', [r'workprint']),
    ('line', [r'line']),
    ('h26x', [r'x26[45]']),
])


def get_icon_path():
    return os.path.join(ADDON_PATH, 'icon.png')


def translation(id_value):
    return ADDON.getLocalizedString(id_value)


def notify(message, image=None):
    dialog = xbmcgui.Dialog()
    dialog.notification(ADDON_NAME, message, icon=image, sound=False)
    del dialog


def human_size(nbytes):
    suffixes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    i = 0
    while nbytes >= 1024 and i < len(suffixes) - 1:
        nbytes /= 1024.
        i += 1
    f = ('%.2f' % nbytes).rstrip('0').rstrip('.')
    return '{} {}'.format(f, suffixes[i])


def get_resolution(name):
    return _search_re_keys(name, resolutions, "resolution", "unknown")


def get_release_type(name):
    return _search_re_keys(name, _release_types, "release type", "unknown")


def _search_re_keys(name, re_dict, log_msg, default=""):
    for result, search_keys in re_dict.iteritems():
        if bool(re.search(r'\W+(' + "|".join(search_keys) + r')\W*', name, re.IGNORECASE)):
            return result

    log.warning("Could not determine %s from filename '%s'", log_msg, name)
    return default
