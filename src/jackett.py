# -*- coding: utf-8 -*-

"""
Burst processing thread
"""

import time
from urlparse import urlparse

import xbmc
import xbmcgui
from elementum.provider import log

import filter
import utils
from client import Jackett
from utils import get_setting

available_providers = 0
special_chars = "()\"':.[]<>/\\?"


def get_client():
    host = urlparse(get_setting('host'))
    if host.netloc == '' or host.scheme == '':
        log.warning("Host %s is invalid. Can't return anything", get_setting('host'))
        utils.notify(utils.translation(32600), image=utils.get_icon_path())
        return None

    api_key = get_setting('api_key')

    if len(api_key) != 32:
        utils.notify(utils.translation(32601), image=utils.get_icon_path())
        return None
    else:
        log.debug("jackett host: %s", host)
        log.debug("jackett api_key: %s%s%s", api_key[0:2], "*" * 26, api_key[-4:])

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

    log.debug("Searching with payload (%s): %s" % (method, repr(payload)))

    p_dialog = xbmcgui.DialogProgressBG()
    p_dialog.create('Elementum [COLOR FFFF6B00]Jackett[/COLOR]', utils.translation(32602))

    try:
        request_start_time = time.time()
        results = search_jackett(payload, method)
        request_end_time = time.time()
        request_time = round(request_end_time - request_start_time, 2)

        log.debug("All results: %s" % repr(results))

        log.info("Jackett returned %d results in %s seconds" % (len(results), request_time))
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

    payload['titles'] = dict((k.lower(), v) for k, v in payload['titles'].iteritems())

    if get_setting('kodi_language', bool):
        kodi_language = xbmc.getLanguage(xbmc.ISO_639_1)
        if not kodi_language:
            log.warning("Kodi returned empty language code...")
        elif kodi_language not in payload.get('titles', {}):
            log.info("No '%s' translation available..." % kodi_language)
        else:
            payload["search_title"] = payload["titles"][kodi_language]

    if "search_title" not in payload:
        payload["search_title"] = unicode.encode(payload["title"])

    return payload


def filter_results(method, results):
    log.debug("results before filtered: %s", repr(results))

    if get_setting('filter_keywords_enabled', bool):
        results = filter.keywords(results)
        log.debug("results after filtering keywords: %s", repr(results))

    if get_setting('filter_size_enabled', bool):
        results = filter.size(method, results)
        log.debug("results after filtering size: %s", repr(results))

    if get_setting('filter_include_resolution_enabled', bool):
        results = filter.resolution(results)
        log.debug("results after filtering resolution: %s", repr(results))

    if get_setting('filter_include_release', bool):
        results = filter.release_type(results)
        log.debug("results after filtering release type: %s", repr(results))

    if get_setting('filter_exclude_no_seed', bool):
        results = filter.seed(results)
        log.debug("results after filter no seeds: %s", repr(results))

    # todo remove dupes
    # todo maybe rating and codec

    log.debug("results after filtering: %s", repr(results))

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

    log.debug("Processing %s with Jackett", method)
    if method == 'movie':
        res = jackett.search_movie(payload["search_title"], payload['year'], payload["imdb_id"])
    elif method == 'season':
        res = jackett.search_season(payload["search_title"], payload["season"], payload["imdb_id"])
    elif method == 'episode':
        res = jackett.search_episode(payload["search_title"], payload["season"], payload["episode"], payload["imdb_id"])
    elif method == 'anime':
        log.warning("jackett provider does not yet support anime search")
        res = []
        log.info("anime payload=%s", repr(payload))
    #     client.search_query(payload["search_title"], payload["season"], payload["episode"], payload["imdb_id"])
    else:
        res = jackett.search_query(payload["search_title"])

    log.debug("%s search returned %d results", method, len(res))

    res = filter_results(method, res)

    return sort_results(res)
