# -*- coding: utf-8 -*-

"""
Burst processing thread
"""

import time
from urllib.parse import urlparse

from kodi_six import xbmc, xbmcgui
from elementum.provider import log

import filter, utils
from client import Jackett
from utils import get_setting

available_providers = 0
special_chars = "()\"':.[]<>/\\?"


def get_client():
    host = urlparse(get_setting('host'))
    if host.netloc == '' or host.scheme == '':
        log.warning(f"Host {get_setting('host')} is invalid. Can't return anything")
        utils.notify(utils.translation(32600), image=utils.get_icon_path())
        return None

    api_key = get_setting('api_key')

    if len(api_key) != 32:
        utils.notify(utils.translation(32601), image=utils.get_icon_path())
        return None
    else:
        log.debug(f"jackett host: {host}")
        log.debug(f"jackett api_key: {api_key[0:2]}{'*' * 26}{api_key[-4:]}")

    return Jackett(host=host.geturl(), api_key=api_key)


def validate_client():
    p_dialog = xbmcgui.DialogProgressBG()
    try:
        p_dialog.create('Elementum [COLOR FFFF6B00]Jackett[/COLOR]', utils.translation(32005))
        get_client()
        if get_setting("settings_validated") == "Success":
            utils.notify(utils.translation(32006), image=utils.get_icon_path())
        utils.ADDON.openSettings()
    finally:
        p_dialog.close()
        del p_dialog


def search(payload, method="general"):
    payload = parse_payload(method, payload)

    log.debug(f"Searching with payload ({method}): f{payload}")

    p_dialog = xbmcgui.DialogProgressBG()
    p_dialog.create('Elementum [COLOR FFFF6B00]Jackett[/COLOR]', utils.translation(32602))

    try:
        request_start_time = time.time()
        results = search_jackett(payload, method)
        request_end_time = time.time()
        request_time = round(request_end_time - request_start_time, 2)

        log.debug(f"All results: {results}")

        log.info(f"Jackett returned {len(results)} results in {request_time} seconds")
    finally:
        p_dialog.close()
        del p_dialog

    return results


def parse_payload(method, payload):
    if method == 'general':
        if 'query' in payload:
            payload['title'] = payload['query']
            payload['titles'] = {
                'source': payload['query']
            }
        else:
            payload = {
                'title': payload,
                'titles': {
                    'source': payload
                },
            }

    payload['titles'] = dict((k.lower(), v) for k, v in list(payload['titles'].items()))

    if get_setting('kodi_language', bool):
        kodi_language = xbmc.getLanguage(xbmc.ISO_639_1)
        if not kodi_language:
            log.warning("Kodi returned empty language code...")
        elif kodi_language not in payload.get('titles', {}):
            log.info(f"No '{kodi_language}' translation available...")
        else:
            payload["search_title"] = payload["titles"][kodi_language]

    if "search_title" not in payload:
        log.info(f"Could not determine search title, falling back to normal title: {payload['title']}")
        payload["search_title"] = payload["title"]

    return payload


def filter_results(method, results):
    log.debug(f"results before filtered: {results}")

    if get_setting('filter_keywords_enabled', bool):
        results = filter.keywords(results)
        log.debug(f"results after filtering keywords: {results}")

    if get_setting('filter_size_enabled', bool):
        results = filter.size(method, results)
        log.debug(f"results after filtering size: {results}")

    if get_setting('filter_include_resolution_enabled', bool):
        results = filter.resolution(results)
        log.debug(f"results after filtering resolution: {results}")

    if get_setting('filter_include_release', bool):
        results = filter.release_type(results)
        log.debug(f"results after filtering release type: {results}")

    if get_setting('filter_exclude_no_seed', bool):
        results = filter.seed(results)
        log.debug(f"results after filtering no seeds: {results}")

    # todo remove dupes
    # todo maybe rating and codec

    log.debug(f"results after filtering: {results}")

    return results


def sort_results(results):
    sort_by = get_setting('sort_by', int)
    # 0 "Resolution"
    # 1 "Seeds"
    # 2 "Size"
    # 3 "Balanced"

    if sort_by == 0:
        sorted_results = sorted(results, key=lambda r: r["resolution"], reverse=True)
    elif sort_by == 1:
        sorted_results = sorted(results, key=lambda r: r['seeds'], reverse=True)
    elif sort_by == 2:
        sorted_results = sorted(results, key=lambda r: r['size'], reverse=True)
    else:
        # todo do something more advanced with the "balanced" option
        sorted_results = sorted(results, key=lambda r: r["seeds"] * 3 * r["resolution"], reverse=True)

    return sorted_results


def search_jackett(payload, method):
    jackett = get_client()
    if jackett is None:
        utils.notify(utils.translation(32603), image=utils.get_icon_path())
        return []

    log.debug(f"Processing {method} with Jackett")
    if method == 'movie':
        res = jackett.search_movie(payload["search_title"], payload['year'], payload["imdb_id"])
    elif method == 'season':
        res = jackett.search_season(payload["search_title"], payload["season"], payload["imdb_id"])
    elif method == 'episode':
        res = jackett.search_episode(payload["search_title"], payload["season"], payload["episode"], payload["imdb_id"])
    elif method == 'anime':
        log.warning("jackett provider does not yet support anime search")
        res = []
        log.info(f"anime payload={payload}")
    #     client.search_query(payload["search_title"], payload["season"], payload["episode"], payload["imdb_id"])
    else:
        res = jackett.search_query(payload["search_title"])

    log.debug(f"{method} search returned {len(res)} results")

    res = filter_results(method, res)

    return sort_results(res)
