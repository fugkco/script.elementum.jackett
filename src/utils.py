# coding=utf-8
import hashlib
import os
import re
import itertools
from collections import OrderedDict

from kodi_six import xbmcgui

import addon
from logger import log

_plugin_setting_prefix = "elementum.jackett."

PROVIDER_COLOR_MIN_BRIGHTNESS = 50

UNKNOWN = 'unknown'

resolutions = OrderedDict([
    ('4k', [r'4k', r'2160[p]', r'uhd', r'4k', r'hd4k']),
    ('2k', [r'1440[p]', r'2k']),
    ('1080p', [r'1080[ip]', r'1920x1080', r'hd1080p?', r'fullhd', r'fhd', r'blu\W*ray', r'bd\W*remux']),
    ('720p', [r'720[p]', r'1280x720', r'hd720p?', r'hd\-?rip', r'b[rd]rip']),
    ('480p', [r'480[p]', r'xvid', r'dvd', r'dvdrip', r'hdtv', r'web\-(dl)?rip', r'iptv', r'sat\-?rip',
              r'tv\-?rip']),
    ('240p', [r'240[p]', r'vhs\-?rip']),
    (UNKNOWN, []),
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
    (UNKNOWN, [])
])


def get_icon_path(icon='icon.png'):
    return os.path.join(addon.PATH, 'resources', 'images', icon)


def translation(id_value):
    return addon.ADDON.getLocalizedString(id_value)


def notify(message, image=None):
    dialog = xbmcgui.Dialog()
    dialog.notification(addon.NAME, message, icon=image, sound=False)
    del dialog


def human_size(nbytes):
    suffixes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    i = 0
    while nbytes >= 1024 and i < len(suffixes) - 1:
        nbytes /= 1024.
        i += 1
    f = f"{nbytes:.2f}".rstrip('0').rstrip('.')
    return f"{f} {suffixes[i]}"


def get_resolution(name):
    return _search_re_keys(name, resolutions, "resolution", UNKNOWN)


def get_release_type(name):
    return _search_re_keys(name, _release_types, "release type", UNKNOWN)


def _search_re_keys(name, re_dict, log_msg, default=""):
    for result, search_keys in list(re_dict.items()):
        if bool(re.search(r'\W+(' + "|".join(search_keys) + r')\W*', name, re.IGNORECASE)):
            return result

    log.warning(f"Could not determine {log_msg} from filename '{name}'")
    return default


def set_setting(key, value):
    addon.ADDON.setSetting(_plugin_setting_prefix + key, str(value))


def get_setting(key, converter=str, choices=None):
    from elementum.provider import get_setting as original_get_settings
    return original_get_settings(_plugin_setting_prefix + key, converter, choices)


def get_provider_color(provider_name):
    hash = hashlib.sha256(provider_name.encode("utf")).hexdigest()
    colors = []

    spec = 10
    for i in range(0, 3):
        offset = spec * i
        rounded = round(int(hash[offset:offset + spec], 16) / int("F" * spec, 16) * 255)
        colors.append(int(max(rounded, PROVIDER_COLOR_MIN_BRIGHTNESS)))

    while (sum(colors) / 3) < PROVIDER_COLOR_MIN_BRIGHTNESS:
        for i in range(0, 3):
            colors[i] += 10

    for i in range(0, 3):
        colors[i] = f'{colors[i]:02x}'

    return "FF" + "".join(colors).upper()


def check_season_name(title, season_name=""):
    # make sure season name is unique. Not eq to movie title or "season". It saves from false-positive filtering.
    season_name = season_name.lower()
    if season_name in title or "season" in season_name:
        return ""
    return season_name


def concat_list(li):
    """ converts [[a],[b,c]] to [a, b, c] """
    return list(itertools.chain.from_iterable(li))
