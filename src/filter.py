# coding=utf-8
from logger import log
from utils import get_setting, UNKNOWN
import re


#
#
# def get_setting(setting, typ):
#     return typ(
#         {
#             'sort_by': 0,
#
#             'filter_exclude_no_seed': True,
#             'filter_keywords_enabled': False,
#             'keywords_block': '',
#             'keywords_require': '',
#
#             'filter_size_enabled': False,
#             'size_include_unknown': True,
#             'size_min': 0,
#             'size_max': 100,
#             'size_movies_min': 0.5,
#             'size_movies_max': 30,
#             'size_season_min': 0.5,
#             'size_season_max': 10,
#             'size_episode_min': 0,
#             'size_episode_max': 1,
#
#             'filter_include_resolution_enabled': True,
#             'include_resolution_4k': True,
#             'include_resolution_2k': True,
#             'include_resolution_1080p': True,
#             'include_resolution_720p': True,
#             'include_resolution_480p': True,
#             'include_resolution_240p': False,
#             'include_resolution_unknown': False,
#
#             'filter_include_release': True,
#             'include_release_brrip': True,
#             'include_release_webdl': True,
#             'include_release_hdrip': True,
#             'include_release_hdtv': True,
#             'include_release_dvd': True,
#             'include_release_dvdscr': True,
#             'include_release_screener': True,
#             'include_release_3d': False,
#             'include_release_telesync': False,
#             'include_release_cam': False,
#             'include_release_tvrip': True,
#             'include_release_iptvrip': True,
#             'include_release_vhsrip': False,
#             'include_release_trailer': False,
#             'include_release_workprint': False,
#             'include_release_line': False,
#             'include_release_unknown': False,
#         }[setting]
#     )

def keywords(results):
    block_keywords = get_setting('keywords_block').split(",")
    require_keywords = get_setting('keywords_require').split(",")

    for word in block_keywords:
        results = [
            result
            for result in results
            if word in result["name"]
        ]

    for word in require_keywords:
        results = [
            result
            for result in results
            if word not in result["name"]
        ]

    return results


def size(method, results):
    include_unknown = get_setting('size_include_' + UNKNOWN, bool)

    if method in ["movie", "season", "episode"]:
        min_size = get_setting('size_' + method + '_min', float)
        max_size = get_setting('size_' + method + '_max', float)
    else:
        min_size = get_setting('size_min', float)
        max_size = get_setting('size_max', float)

    #                        MB     KB      B
    min_size = min_size * (1024 * 1024 * 1024)
    max_size = max_size * (1024 * 1024 * 1024)

    return [
        result
        for result in results
        if (size == -1 and include_unknown) or (size != -1 and min_size <= result["_size_bytes"] <= max_size)
    ]


def resolution(results):
    filtered = []
    for result in results:
        log.debug(f"res {result['name']}: name={result['_resolution']}; id={result['resolution']}")
        if get_setting('include_resolution_' + result["_resolution"], bool):
            filtered.append(result)

    return filtered


def seed(results):
    return [
        result
        for result in results
        if result["seeds"] > 0
    ]


def unique(results):
    return list({v['info_hash'].lower(): v for v in results}.values())


def release_type(results):
    return [
        result
        for result in results
        if get_setting('include_release_' + result["release_type"], bool)
    ]


def tv_season_episode(results, season, season_name, episode, global_ep, ep_year, season_year=0, start_year=0):
    # Function for sorting large amount of not accurate torrents. Checks year season and episodes.
    # The filtering shouldn't be strict. I'm trying not to lose suitable torrents.
    filtered = []
    for res in results:
        name = res["name"].lower()
        # Remove resolution
        name = re.sub(r"\d+p", '', name)
        log.debug(f"torrent: {name}")

        if season_name and season_name in name:
            filtered.append(res)
            continue

        year_pattern = r"(?P<from>(?:19|20)\d{2})(?:\s*-\s*(?P<to>[12]\d{3}))?"
        y = re.search(year_pattern, name)
        if not y:
            log.debug("No year")
            continue
        y_from = int(y.group("from") or "99999")
        y_to = int(y.group("to") or "-1")
        if (start_year != y_from and ep_year != y_from and season_year != y_from and
                (y_from > season_year or season_year > y_to)):
            log.debug(f"Not suitable year: {ep_year or 'none'} || {season_year or 'none'} || {start_year or 'none'}")
            continue
        # Remove the year from the text
        name_no_year = re.sub(year_pattern, '', name)

        if f"s{season}e{episode}" in name_no_year:
            filtered.append(res)
            continue

        season_pattern = r"\W(?P<s_flag>s|season|сезон|tv-?|тв-?)[\s\(\[\{]*(?P<from>\d+)(?:\s*-\s*(?P<to>\d+))?"
        s = re.search(season_pattern, name_no_year)
        if s:
            s_from = int(s.group("from") or "99999")
            s_to = int(s.group("to") or "-1")
            s_flag = s.group("s_flag")
            if season == s_from or (s_from <= season <= s_to):  # season is suitable
                filtered.append(res)
                continue
            elif s_flag and s_from != 1:  # season is marked but not suitable. If season is first need check episodes
                log.debug(f"Not suitable season: {season or 'none'}")
                continue
            # Remove the season from the text
        else:
            log.debug("No season found")

        if not global_ep:
            continue
        episode_pattern = r"(?:e?(?P<from>\d+)(?:\s*-\s*e?(?P<to>\d+)))|(?P<last>\d+)(?:\s*\+\s*\d*)?(?:\s*(из|of)\s*(?P<all>\d+))"
        e = re.search(episode_pattern, name_no_year)
        while e:
            e_from = int(e.group("from") or "0")
            e_to = int(e.group("to") or "0")
            e_last = int(e.group("last") or "0")
            if (e_from <= global_ep <= e_to) or global_ep <= e_last:
                filtered.append(res)
                break
            name_no_year = re.sub(episode_pattern, '', name_no_year, 1)
            e = re.search(episode_pattern, name_no_year)

    return filtered
