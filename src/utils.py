# coding=utf-8
import hashlib
import os
import re
import itertools
from collections import OrderedDict
from enum import Enum

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
    ('720p', [r'720[p]', r'1280x720', r'hd720p?', r'hd\-?rip', r'b[rd]rip', r'xvid', r'dvd', r'dvdrip', r'hdtv',
              r'web\-(dl)?rip', r'iptv']),
    ('480p', [r'480[p]', r'sat\-?rip', r'tv\-?rip']),
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


class MsgID(Enum):
    JACKETT = 32000
    HOST = 32001
    API_KEY = 32002
    JACKETT_SETTINGS_VALID = 32003
    VALIDATE_SETTINGS = 32004
    VALIDATING = 32005
    SUCCESSFULLY_CONNECTED_TO_JACKETT = 32006
    ENABLE_SEARCH_WITH_IMDB_ID = 32007
    LIMIT_TORRENT_COUNT = 32008
    CONNECTING_TO_JACKETT_FAILED = 32009
    FILTERING = 32050
    GENERAL = 32051
    SORT_RETURNED_RESULTS_BY = 32052
    RESOLUTION = 32053
    SEEDS = 32054
    SIZE = 32055
    BALANCED = 32056
    HIDE_TORRENTS_WITHOUT_SEEDS = 32057
    SECONDARY_SEARCH_FOR_SEASON = 32058
    USE_SMART_FILTER_FOR_SHOWS = 32059
    FILTER_KEYWORDS = 32100
    ENABLE = 32101
    BLOCK = 32102
    REQUIRE = 32103
    FILTER_SIZE = 32150
    INCLUDE_UNKNOWN_FILE_SIZE = 32152
    MIN_SIZE_GB = 32153
    MAX_SIZE_GB = 32154
    MIN_MOVIE_SIZE_GB = 32155
    MAX_MOVIE_SIZE_GB = 32156
    MIN_SEASON_SIZE_GB = 32157
    MAX_SEASON_SIZE_GB = 32158
    MIN_EPISODE_SIZE_GB = 32159
    MAX_EPISODE_SIZE_GB = 32160
    FILTER_RESOLUTION = 32200
    RESOLUTION_ENABLE = 32201
    RESOLUTION_4K = 32202
    RESOLUTION_2K = 32203
    RESOLUTION_1080P = 32204
    RESOLUTION_720P = 32205
    RESOLUTION_480P = 32206
    RESOLUTION_240P = 32207
    RESOLUTION_UNKNOWN = 32208
    FILTER_RELEASE_TYPE = 32250
    RELEASE_TYPE_ENABLE = 32251
    BRRIP_BDRIP_BLURAY = 32252
    WEBDL_WEBRIP = 32253
    HDRIP = 32254
    HDTV = 32255
    DVDRIP = 32256
    H26X = 32257
    DVDSCR = 32258
    SCREENER_SCR = 32259
    RELEASE_TYPE_3D = 32260
    TELE_SYNC_TS_TC = 32261
    CAM_HDCAM = 32262
    TVRIP_SATRIP = 32263
    IPTVRIP = 32264
    VHSRIP = 32265
    TRAILER = 32266
    WORKPRINT = 32267
    LINE = 32268
    RELEASE_TYPE_UNKNOWN = 32269
    ADVANCED = 32300
    DEBUGGER = 32301
    ADDITIONAL_LIBRARIES = 32303
    DEBUGGER_HOST = 32304
    DEBUGGER_PORT = 32305
    JACKETT_HOST_INVALID = 32600
    JACKETT_API_KEY_INVALID = 32601
    SEARCHING = 32602
    UNABLE_TO_CONNECT_TO_JACKETT = 32603
    REQUESTING_RESULTS_FROM_JACKETT = 32604
    JACKETT_ERROR = 32700
    UNABLE_TO_DETERMINE_JACKETT_CAPABILITIES = 32701
    JACKETT_UNABLE_TO_SEARCH = 32702
    CRITICAL_ERROR = 32703
    JACKETT_TIMEOUT = 32704
    JACKETT_CLIENT_ERR = 32705
    FILTERING_RESULT = 32750
    RESOLVED_MAGNET_LINKS = 32751
    WAITING = 32752
    SORTING = 32753
    REQUESTS_DONE = 32754
    RETURNING_TO_ELEMENTUM = 32755
    ADDON_IS_PROVIDER = 32800


def get_icon_path(icon='icon.png'):
    return os.path.join(addon.PATH, 'resources', 'images', icon)


def get_localized_string(key: MsgID):
    """Fetches the localized string for the given key."""
    if isinstance(key, MsgID):
        return translation(key.value)
    else:
        log.warn(f"'{key}' translation not found. Please fix MsgID enum")
        return f"'{key}' translation not found"


def translation(id_value):
    return addon.ADDON.getLocalizedString(id_value)


def notify(message, image=None):
    dialog = xbmcgui.Dialog()
    dialog.notification(addon.NAME, message, icon=image, sound=False, time=5000)
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


def concat_dicts(dicts):
    d4 = {}
    for d in dicts:
        d4.update(d)
    return d4


def is_english(s):
    try:
        s.encode(encoding='utf-8').decode('ascii')
    except UnicodeDecodeError:
        return False
    else:
        return True
