# -*- coding: utf-8 -*-

"""
Burst processing thread
"""

import traceback
from urllib.parse import urlparse

import time
from kodi_six import xbmc, xbmcgui

import addon
import filter
import utils
from client import Jackett
from logger import log
from utils import get_setting

available_providers = 0
special_chars = "()\"':.[]<>/\\?"


def get_client(p_dialog: xbmcgui.DialogProgressBG = None):
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

    return Jackett(host=host.geturl(), api_key=api_key, p_dialog=p_dialog)


def validate_client():
    p_dialog = xbmcgui.DialogProgressBG()
    try:
        p_dialog.create('Elementum [COLOR FFFF6B00]Jackett[/COLOR]', utils.translation(32005))
        get_client()
        if get_setting("settings_validated") == "Success":
            utils.notify(utils.translation(32006), image=utils.get_icon_path())
        addon.ADDON.openSettings()
    finally:
        p_dialog.close()
        del p_dialog


def search(payload, method="general"):
    log.info(f"got req from elementum:{payload}")
    payload = parse_payload(method, payload)

    log.debug(f"Searching with payload ({method}): f{payload}")

    p_dialog = xbmcgui.DialogProgressBG()
    p_dialog.create('Elementum [COLOR FFFF6B00]Jackett[/COLOR]', utils.translation(32602))
    results = []

    try:
        request_start_time = time.time()
        results = search_jackett(p_dialog, payload, method)
        request_end_time = time.time()
        request_time = round(request_end_time - request_start_time, 2)

        log.debug(f"All results: {results}")

        log.info(f"Jackett returned {len(results)} results in {request_time} seconds")
    except Exception:
        utils.notify(utils.translation(32703))
        log.error(f"Got exception: {traceback.format_exc()}")
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

    payload['season_name'] = utils.check_season_name(payload["search_title"], payload.get('season_name', ""))

    return payload


def filter_results(method, results, season, season_name, episode, global_ep, ep_year, season_year=0, start_year=0):
    log.debug(f"results before filtered: {results}")

    if get_setting('filter_keywords_enabled', bool):
        log.info(f"filtering keywords {len(results)}")
        results = filter.keywords(results)
        log.debug(f"filtering keywords results: {results}")

    if get_setting('filter_size_enabled', bool):
        log.info(f"filtering size {len(results)}")
        results = filter.size(method, results)
        log.debug(f"filtering size results: {results}")

    if get_setting('filter_include_resolution_enabled', bool):
        log.info(f"filtering resolution {len(results)}")
        results = filter.resolution(results)
        log.debug(f"filtering resolution results: {results}")

    if get_setting('filter_include_release', bool):
        log.info(f"filtering release type {len(results)}")
        results = filter.release_type(results)
        log.debug(f"filtering release type results: {results}")

    if get_setting('filter_exclude_no_seed', bool):
        log.info(f"filtering no seeds {len(results)}")
        results = filter.seed(results)
        log.debug(f"filtering no seeds results: {results}")

    if method == "episode" and get_setting("use_smart_show_filter", bool):
        log.info(f"smart-filtering show torrents {len(results)}")
        results = filter.tv_season_episode(results, season, season_name, episode, global_ep, ep_year, season_year,
                                           start_year)
        log.debug(f"smart-filtering show torrents results: {results}")

    # todo maybe rating and codec

    log.debug(f"Resulted in {len(results)} results: {results}")

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


def search_jackett(p_dialog, payload, method):
    jackett = get_client(p_dialog)
    if jackett is None:
        utils.notify(utils.translation(32603), image=utils.get_icon_path())
        return []

    log.debug(f"Processing {method} with Jackett")
    p_dialog.update(message=utils.translation(32604))
    if method == 'movie':
        res = jackett.search_movie(payload["search_title"], payload['year'], payload["imdb_id"])
    elif method == 'season':
        res = jackett.search_season(payload["search_title"], payload["season"], payload["imdb_id"])
    elif method == 'episode':
        if get_setting("use_smart_show_filter", bool):
            res = jackett.search_title(payload["search_title"], payload["imdb_id"])
        else:
            res = jackett.search_episode(payload["search_title"], payload["season"], payload["episode"],
                                         payload["imdb_id"])
    elif method == 'anime':
        log.warn("jackett provider does not yet support anime search")
        res = []
        log.info(f"anime payload={payload}")
    #     client.search_query(payload["search_title"], payload["season"], payload["episode"], payload["imdb_id"])
    else:
        res = jackett.search_query(payload["search_title"])

    log.debug(f"{method} search returned {len(res)} results")
    p_dialog.update(25, message=utils.translation(32750))
    res = filter_results(method, res, payload.get('season', None), payload.get('season_name', ""),
                         payload.get('episode', None), payload.get('absolute_number', None), payload.get('year', None),
                         payload.get('season_year', None), payload.get('show_year', None))

    res = jackett.async_magnet_resolve(res)

    p_dialog.update(90, message=utils.translation(32752))
    res = filter.unique(res)
    log.info(f"filtering for unique items {len(res)}")
    log.debug(f"unique items results: {res}")

    p_dialog.update(95, message=utils.translation(32753))
    res = sort_results(res)

    p_dialog.update(100, message=utils.translation(32754))
    return res[:get_setting('max_results', int)]
