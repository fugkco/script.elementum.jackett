#!/usr/bin/env python3.6
# coding=utf-8
import time
import aiohttp
import asyncio
from enum import Enum, Flag, auto
from http import HTTPStatus
import xml.etree.ElementTree as ElT
from xml.etree import ElementTree

import utils
from logger import log
from pdialoghelper import PDialog
from utils import notify, translation, get_icon_path, human_size, get_resolution, get_release_type, get_setting, \
    set_setting


class Cap(Flag):
    QUERY = auto()
    SEASON = auto()
    EPISODE = auto()
    IMDBID = auto()
    TVDBID = auto()
    GENRE = auto()
    YEAR = auto()


class SearchType(Enum):
    COMMON = "search"
    MOVIE = "movie"
    TV = "tvsearch"


flags_mapping = {
    "q": Cap.QUERY,
    "season": Cap.SEASON,
    "ep": Cap.EPISODE,
    "imdbid": Cap.IMDBID,
    "tvdbid": Cap.TVDBID,
    "genre": Cap.GENRE,
    "year": Cap.YEAR
}


def parse_cap(atr_arr):
    r = Cap(0)
    for atr in atr_arr:
        r |= flags_mapping.get(atr, Cap(0))
    return r


class Indexer:

    def __init__(self, root):
        self.id = root.get("id")
        self.name = root.find("title").text
        self.tv_enabled = root.find("./caps/searching/tv-search").get("available") == "yes"
        self.movie_enabled = root.find("./caps/searching/movie-search").get("available") == "yes"

        tv_p = root.find("./caps/searching/tv-search").get("supportedParams").lower().split(",")
        self.tv_caps = parse_cap(tv_p)
        movie_p = root.find("./caps/searching/movie-search").get("supportedParams").lower().split(",")
        self.movie_caps = parse_cap(movie_p)

    def check_t_and_cap(self, t):
        if t == SearchType.MOVIE and self.movie_enabled:
            cap = self.movie_caps
        elif t == SearchType.TV and self.tv_enabled:
            cap = self.tv_caps
        else:
            t = SearchType.COMMON
            cap = Cap.QUERY
        return t, cap


class JackettClient:
    #  get list of configured indexers
    get_indexers_list = "/api/v2.0/indexers/all/results/torznab?t=indexers&configured=true"
    query_by_indexer = "/api/v2.0/indexers/{indexer}/results/torznab"

    def __init__(self, host, api_key):
        self.host = host
        self.api_key = api_key
        self.indexers = []
        self.session = None

    async def create_session(self, host=None):
        timeout = aiohttp.ClientTimeout(20)
        self.session = aiohttp.ClientSession(host or self.host, timeout=timeout)

    async def close_session(self):
        if not self.session.closed:
            await self.session.close()

    async def send_request(self, url, params=None):
        log.info(f"Sending to Jackett url: {url} params: {params}")
        if params is None:
            params = {}
        params['apikey'] = self.api_key
        start = time.monotonic()
        async with self.session.get(url, params=params) as resp:
            log.debug(f"Indexers request status: {resp.status}")
            if resp.status != HTTPStatus.OK:
                self.proceed_resp_error(resp.status, await resp.text())
                return
            response_time = time.monotonic() - start
            body = await resp.text()

        log.info(f"Jackett returned response in {response_time:.3f}s size {len(body)} b")

        root = ElT.fromstring(body)
        if root.tag == "error":
            self.proceed_resp_error(root.attrib['code'], root.attrib['description'])
            return
        set_setting('settings_validated', 'Success')
        return root

    async def request_indexers(self):
        try:
            root = await self.send_request(self.get_indexers_list)
        except asyncio.TimeoutError as e:
            log.warn(f"Request to {self.get_indexers_list} timed out: {e}")
            utils.notify(utils.get_localized_string(utils.MsgID.JACKETT_TIMEOUT))
            return
        except aiohttp.ClientError as e:
            log.error(f"Request to {self.get_indexers_list} failed with exception: {e}")
            utils.notify(utils.get_localized_string(utils.MsgID.JACKETT_CLIENT_ERR))
            return

        if not root:
            return
        self.indexers.clear()
        for i_root in root.findall('indexer'):
            self.indexers.append(Indexer(i_root))
        return self.indexers

    async def search_by_indexer(self, indexer, t, title, year, season=None, ep=None, imdb_id=None):
        t, cap = indexer.check_t_and_cap(t)
        # set params
        params = {'t': t.value}
        if imdb_id and (cap & Cap.IMDBID) and get_setting('search_by_imdb_key', bool):
            params["imdbid"] = imdb_id
            season = ep = None
        elif year and (cap & Cap.YEAR):
            params["q"] = title
            params["year"] = year
        else:
            params["q"] = f"{title}"
            if year:
                params["q"] += f" {year}"

        if bool(season) and (cap & Cap.SEASON):
            params["season"] = season
            if bool(ep) and (cap & Cap.EPISODE):
                params["ep"] = ep
        elif bool(season):
            params["q"] += " S{:0>2}".format(season)
            if bool(ep):
                params["q"] += "E{:0>2}".format(ep)

        url = self.query_by_indexer.format(indexer=indexer.id)
        try:
            root = await self.send_request(url, params)
        except asyncio.TimeoutError as e:
            log.warn(f"Request to {url} timed out: {e}")
            return {}, indexer
        except aiohttp.ClientError as e:
            log.error(f"Request to {url} failed with exception: {e}")
            return {}, indexer

        if not root:
            return {}, indexer
        torr_list = parse_torrents(root)
        log.info(f"Done searching. Got {len(torr_list)} torrents from {indexer.name}.")
        return torr_list, indexer

    async def await_indexers(self, tasks, pd_cb):
        def update_p_dialog():
            if pd_cb:
                pd_cb(count, total, utils.translation(32754).format(PDialog.default_heading, count, total),
                      utils.translation(32752).format(', '.join(set(await_ind_names))))

        result = []
        total = len(tasks)
        count = 0
        await_ind_names = [i.name for i in self.indexers] * (
                    total // len(self.indexers))  # multipy in case multiple searches
        update_p_dialog()
        for task in asyncio.as_completed(tasks):
            torrents, indexer = await task
            count += 1
            await_ind_names.remove(indexer.name)
            update_p_dialog()
            result.append(torrents)
        return result

    async def search_movie(self, title, year=None, imdb_id=None, p_dialog_cb=None):
        tasks = [self.search_by_indexer(ind, SearchType.MOVIE, title, year, imdb_id=imdb_id) for ind in self.indexers]
        torrent_dicts = await self.await_indexers(tasks, p_dialog_cb)
        return utils.concat_dicts(torrent_dicts).values()

    async def search_tv(self, title, year=None, season=None, ep=None, imdb_id=None, p_dialog_cb=None):
        tasks = [self.search_by_indexer(ind, SearchType.TV, title, year, season, ep, imdb_id) for ind in
                 self.indexers]
        if get_setting("search_season_on_episode", bool) and bool(season) and bool(ep):
            tasks += [self.search_by_indexer(ind, SearchType.TV, title, year, season, imdb_id=imdb_id) for ind in
                      self.indexers]
        torrent_dicts = await self.await_indexers(tasks, p_dialog_cb)
        return utils.concat_dicts(torrent_dicts).values()

    async def search_query(self, title, year=None, imdb_id=None, p_dialog_cb=None):
        tasks = [self.search_by_indexer(ind, SearchType.COMMON, title, year, imdb_id=imdb_id) for ind in self.indexers]
        torrent_dicts = await self.await_indexers(tasks, p_dialog_cb)
        return utils.concat_dicts(torrent_dicts).values()

    async def search_tv_smart(self, title, ep_year=None, season_year=None, show_year=None, p_dialog_cb=None):
        tasks = [self.search_by_indexer(ind, SearchType.TV, title, None) for ind in self.indexers]
        if ep_year and ep_year != season_year:
            tasks += [self.search_by_indexer(ind, SearchType.TV, title, ep_year) for ind in self.indexers]
        if season_year and season_year != show_year:
            tasks += [self.search_by_indexer(ind, SearchType.TV, title, season_year) for ind in self.indexers]
        if show_year:
            tasks += [self.search_by_indexer(ind, SearchType.TV, title, show_year) for ind in self.indexers]
        torrent_dicts = await self.await_indexers(tasks, p_dialog_cb)
        return utils.concat_dicts(torrent_dicts).values()

    @staticmethod
    def proceed_resp_error(code, description):
        notify(translation(32700).format(code), image=get_icon_path())
        log.error(f"got code {code}: {description}")
        set_setting('settings_validated', description)
        return


def parse_torrents(root):
    results = {}
    items = root.findall("channel/item")
    for item in items:
        result = parse_item(item)
        if result is not None:
            results[result['name']] = result
    return results


def parse_item(item):
    torznab_ns = "http://torznab.com/schemas/2015/feed"

    torznab_elementum_mappings = {
        "tags": {
            "title": "name",
            "jackettindexer": "provider",
            "size": "size",
        },
        "torznab_attrs": {
            "magneturl": "uri",
            "seeders": "seeds",
            "peers": "peers",
            "infohash": "info_hash",
        }
    }

    result = {
        "name": None,
        "provider": "Unknown",
        "size": "Unknown",
        "uri": None,
        "seeds": "0",
        "peers": "0",
        "info_hash": "",
        "language": None,

        # nice to assign correct icons but that can be very time consuming due to the number of indexers in Jackett
        "icon": get_icon_path(),

        "_size_bytes": -1
    }

    for ref in item:
        tag = ref.tag
        attrib = ref.attrib
        if tag == "{" + torznab_ns + "}attr":
            val = attrib["value"]
            if "name" in attrib and "value" in attrib and attrib["name"] and val and \
                    attrib["name"] in torznab_elementum_mappings["torznab_attrs"]:
                json = torznab_elementum_mappings["torznab_attrs"][attrib["name"]]
                result[json] = val
            continue

        if ref.tag in torznab_elementum_mappings["tags"] and ref.text is not None:
            json = torznab_elementum_mappings["tags"][ref.tag]
            val = ref.text.strip()

            result[json] = val

    if result["uri"] is None:
        link = item.find('link')
        jackett_uri = ""
        if link is not None:
            jackett_uri = link.text
        else:
            enclosure = item.find('enclosure')
            if enclosure is not None:
                jackett_uri = enclosure.attrib['url']

        if jackett_uri != "":
            result["uri"] = jackett_uri

    if result["name"] is None or result["uri"] is None:
        log.warning(f"Could not parse item; name = {result['name']}; uri = {result['uri']}")
        log.debug(f"Failed item is: {ElementTree.tostring(item, encoding='utf8')}")
        return None

    provider_color = utils.get_provider_color(result["provider"])

    # result["name"] = result["name"].decode("utf-8") # might be needed for non-english items
    result["seeds"] = int(result["seeds"])
    result["peers"] = int(result["peers"])
    resolution = get_resolution(result["name"])
    result["resolution"] = list(utils.resolutions.keys())[::-1].index(resolution)
    result["_resolution"] = resolution
    result["release_type"] = get_release_type(result["name"])
    result["provider"] = f'[COLOR {provider_color}]{result["provider"]}[/COLOR]'

    if result["size"] != "Unknown":
        result["_size_bytes"] = int(result["size"])
        result["size"] = human_size(result["_size_bytes"])

    log.debug("final item: {}".format(result))

    return result
