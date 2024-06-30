# -*- coding: utf-8 -*-

"""
Burst processing thread
"""

import traceback
from urllib.parse import urlparse

import time
import asyncio
from kodi_six import xbmc, xbmcgui

import addon
import filter
import utils
import torrent
from client import JackettClient
from logger import log
from utils import get_setting
from pdialoghelper import PDialog

available_providers = 0
special_chars = "()\"':.[]<>/\\?"


async def get_client():
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
    cli = JackettClient(host=host.geturl(), api_key=api_key)
    await cli.create_session()
    await cli.request_indexers()
    return cli


async def validate_client():
    cli = await get_client()
    try:
        if get_setting("settings_validated") == "Success":
            utils.notify(utils.translation(32006), image=utils.get_icon_path())
        else:
            utils.notify(utils.translation(32009), image=utils.get_icon_path())
        addon.ADDON.openSettings()
    finally:
        await cli.close_session()
        del cli



def search(payload, method="general"):
    try:
        log.info(f"got req from elementum:{payload}")
        payload = parse_payload(method, payload)

        log.debug(f"Searching with payload ({method}): f{payload}")
        results = []
        p_dialog = PDialog(utils.translation(32602))

        request_start_time = time.time()
        results = asyncio.run(search_jackett(p_dialog, payload, method))
        request_end_time = time.time()
        request_time = round(request_end_time - request_start_time, 2)

        log.debug(f"All results: {results}")

        log.info(f"{len(results)} torrents returned from Jackett in {request_time} seconds")
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
        log.warn(f"Could not determine search language for title")
        if utils.is_english(payload['title']):
            log.info(f"falling back to original_en title: {payload['title']}")
            payload["search_title"] = payload["title"]
        elif "en" in payload["titles"]:
            log.info(f"falling back to not original english title: {payload['titles']['en']}")
            payload["search_title"] = payload["titles"]["en"]
        else:
            log.warn(f"no original english title found. Using: {payload['title']}")
            payload["search_title"] = payload["title"]

    payload['season_name'] = utils.check_season_name(payload["search_title"], payload.get('season_name', ""))

    return payload


def filter_results(method, results, season, season_name, episode, global_ep, ep_year, season_year=0, start_year=0):
    log.debug(f"results before filtered: {results}")

    if get_setting('filter_keywords_enabled', bool):
        log.info(f"{len(results)} ... filtering keywords ")
        results = filter.keywords(results)
        log.debug(f"filtering keywords results: {results}")

    if get_setting('filter_size_enabled', bool):
        log.info(f"{len(results)} ... filtering size")
        results = filter.size(method, results)
        log.debug(f"filtering size results: {results}")

    if get_setting('filter_include_resolution_enabled', bool):
        log.info(f"{len(results)} ... filtering resolution")
        results = filter.resolution(results)
        log.debug(f"filtering resolution results: {results}")

    if get_setting('filter_include_release', bool):
        log.info(f"{len(results)} ... filtering release type")
        results = filter.release_type(results)
        log.debug(f"filtering release type results: {results}")

    if get_setting('filter_exclude_no_seed', bool):
        log.info(f"{len(results)} ... filtering no seeds")
        results = filter.seed(results)
        log.debug(f"filtering no seeds results: {results}")

    if method == "episode" and get_setting("use_smart_show_filter", bool):
        log.info(f"{len(results)} ... smart-filtering show torrents")
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


async def search_jackett(p_dialog, payload, method):
    p_dialog.update(0, message="Getting indexers list")
    j_cli = await get_client()
    try:
        if j_cli is None:
            utils.notify(utils.translation(32603), image=utils.get_icon_path())
            return []

        log.debug(f"Processing {method} with Jackett")
        p_dialog.update(5, message=utils.translation(32604))
        query_weight = 50
        if method == 'movie':
            res = await j_cli.search_movie(payload["search_title"], payload['year'], imdb_id=payload["imdb_id"],
                                           p_dialog_cb=p_dialog.callback(query_weight))
        elif method in ('season', 'episode', 'anime'):
            if get_setting("use_smart_show_filter", bool):
                res = await j_cli.search_tv_smart(payload["search_title"], payload.get('year', None),
                                                  payload.get('season_year', None), payload.get('show_year', None),
                                                  p_dialog_cb=p_dialog.callback(query_weight))
            else:
                res = await j_cli.search_tv(payload["search_title"], season=payload.get("season", None),
                                            ep=payload.get("episode", None), imdb_id=payload["imdb_id"],
                                            p_dialog_cb=p_dialog.callback(query_weight))
        else:
            res = j_cli.search_query(payload["search_title"], p_dialog_cb=p_dialog.callback(query_weight))
    finally:
        await j_cli.close_session()

    log.debug(f"Filtering {len(res)} torrents")
    p_dialog.update(heading=utils.translation(32602), message=utils.translation(32750))
    res = filter_results(method, res, payload.get('season', None), payload.get('season_name', ""),
                         payload.get('episode', None), payload.get('absolute_number', None), payload.get('year', None),
                         payload.get('season_year', None), payload.get('show_year', None))

    log.info(f"{len(res)} ... resolving unique magnets ")
    res = await torrent.uri_to_magnets_uniq_torrents(res, p_dialog.callback(100))
    log.debug(f"Resolving unique magnets results: {res}")

    p_dialog.update(message=utils.translation(32753))
    res = sort_results(res)

    p_dialog.update(message=utils.translation(32754))
    return res[:get_setting('max_results', int)]
