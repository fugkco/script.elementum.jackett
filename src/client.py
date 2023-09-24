#!/usr/bin/env python3.6
# coding=utf-8
import concurrent.futures
import http.client as httplib
import os
import re
import xml.etree.ElementTree as ET
from urllib.parse import urljoin
from xml.etree import ElementTree

from kodi_six import xbmcgui
from requests_toolbelt import sessions

import torrent
import utils
from logger import log
from utils import notify, translation, get_icon_path, human_size, get_resolution, get_release_type, get_setting, \
    set_setting


class Jackett(object):
    """docstring for Jackett"""

    _torznab_ns = "http://torznab.com/schemas/2015/feed"

    _torznab_elementum_mappings = {
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

    def __init__(self, host, api_key, p_dialog: xbmcgui.DialogProgressBG = None):
        super(Jackett, self).__init__()
        self.p_dialog = p_dialog
        self._api_key = api_key
        self._caps = {}

        self._session = sessions.BaseUrlSession(base_url=urljoin(host, "/api/v2.0/indexers/"))
        self.get_caps()

    def get_error(self, content):
        xml = ET.ElementTree(ET.fromstring(content)).getroot()
        if xml.tag == "error":
            return xml.attrib

        return None

    def get_caps(self):
        caps_resp = self._session.get("all/results/torznab", params={"t": "caps", "apikey": self._api_key})

        if caps_resp.status_code != httplib.OK:
            notify(translation(32700).format(caps_resp.reason), image=get_icon_path())
            log.error(f"Jackett return {caps_resp.reason}")
            set_setting('settings_validated', caps_resp.reason)
            return

        err = self.get_error(caps_resp.content)
        if err is not None:
            notify(translation(32700).format(err["description"]), image=get_icon_path())
            log.error(f"got code {err['code']}: {err['description']}")
            set_setting('settings_validated', err["description"])
            return

        set_setting('settings_validated', 'Success')

        xml = ET.ElementTree(ET.fromstring(caps_resp.content)).getroot()

        # todo handle gracefully, doesn't exist for individual trackers
        # self._caps["limits"] = xml.find("limits").attrib

        self._caps["search_tags"] = {}
        for type_tag in xml.findall('searching/*'):
            self._caps["search_tags"][type_tag.tag] = {
                "enabled": type_tag.attrib["available"] == "yes",
                "params": [p for p in type_tag.attrib['supportedParams'].split(",") if p],
            }

        log.info(f"Found capabilities: {self._caps}")
        # todo maybe categories are needed?

    def search_movie(self, title, year, imdb_id):
        if "search_tags" not in self._caps:
            notify(translation(32701), image=get_icon_path())
            return []

        movie_search_caps = self._caps["search_tags"]['movie-search']
        if not movie_search_caps['enabled']:
            notify(translation(32702).format("movie"), image=get_icon_path())
            log.warning("Jackett has no movie capabilities, please add a indexer that has movie capabilities. "
                        "Falling back to query search...")
            return self.search_query(title + ' ' + str(year))

        # todo what values are possible for imdb_id?
        movie_params = movie_search_caps["params"]
        request_params = {
            "t": "movie",
        }

        has_imdb_caps = 'imdbid' in movie_params
        log.debug(f"movie search; imdb_id={imdb_id}, has_imdb_caps={has_imdb_caps}")
        if imdb_id and has_imdb_caps and get_setting('search_by_imdb_key', bool):
            request_params["imdbid"] = imdb_id
        else:
            request_params["q"] = title + ' ' + str(year)
            log.debug(f"searching movie with query={request_params['q']}")

        return self._do_search_request(request_params)

    def search_shows(self, title, season=None, episode=None, imdb_id=None):
        if "search_tags" not in self._caps:
            notify(translation(32701), image=get_icon_path())
            return []

        tv_search_caps = self._caps["search_tags"]['tv-search']
        if not tv_search_caps['enabled']:
            notify(translation(32702).format("show"), image=get_icon_path())
            log.warning("Jackett has no tvsearch capabilities, please add a indexer that has tvsearch capabilities. "
                        "Falling back to query search...")

            title_ep = title
            if bool(season):
                title_ep = "{} S{:0>2}".format(title_ep, season)
                if bool(episode):
                    title_ep = "{}E{:0>2}".format(title_ep, episode)

            results = self.search_query(title_ep)
            if get_setting("search_season_on_episode", bool) and bool(season) and bool(episode):
                season_query = re.escape("{:0>2}".format(season))
                results = results + self._filter_season(self.search_query("{} S{}".format(title, season_query)), season)

            return results

        # todo what values are possible for imdb_id?
        tv_params = tv_search_caps["params"]
        request_params = {
            "t": "tvsearch",
        }
        has_imdb_caps = 'imdbid' in tv_params
        log.debug(f"movie search; imdb_id={imdb_id}, has_imdb_caps={has_imdb_caps}")
        if imdb_id and has_imdb_caps and get_setting('search_by_imdb_key', bool):
            request_params["imdbid"] = imdb_id
        else:
            log.debug(f"searching tv show with query={title}, season={season}, episode={episode}")
            request_params["q"] = title
            if bool(season) and 'season' in tv_params:
                request_params["season"] = season
            if bool(episode) and 'ep' in tv_params:
                request_params["ep"] = episode

        results = self._do_search_request(request_params)
        if get_setting("search_season_on_episode", bool) and 'season' in request_params and 'ep' in request_params:
            del request_params['ep']
            results = results + self._filter_season(self._do_search_request(request_params), season)

        return results

    def _filter_season(self, results, season):
        season_query = re.escape("{:0>2}".format(season))
        s_re = re.compile(r'\bS(eason[\s.]?)?' + season_query + r'\b', re.IGNORECASE)
        ep_re = re.compile(r'\bE(p(isode)?[\s.]?)?\d+\b', re.IGNORECASE)

        return [
            result for result in results
            if s_re.search(result['name']) and not ep_re.search(result['name'])
        ]

    def search_title(self, title, imdb_id):
        return self.search_shows(title, imdb_id=imdb_id)

    def search_season(self, title, season, imdb_id):
        return self.search_shows(title, season=season, imdb_id=imdb_id)

    def search_episode(self, title, season, episode, imdb_id):
        return self.search_shows(title, season=season, episode=episode, imdb_id=imdb_id)

    def search_query(self, query):
        if not self._caps["search_tags"]['search']:
            notify(translation(32702).format("query"), image=get_icon_path())
            log.warning("Jackett has no search capabilities, please add a indexer that has search capabilities.")
            return []

        request_params = {
            "q": query
        }

        return self._do_search_request(request_params)

    def _get_with_progress(self, *args, **kwargs):
        if not self.p_dialog:
            r = self._session.get(*args, **kwargs)
            return r, r.content

        prog_from, prog_to = 0, 25
        self._update_progress(prog_from, prog_to, 0, 100)

        r = self._session.get(stream=True, *args, **kwargs)
        total_size = int(r.headers.get('content-length', 0))
        search_resp = b""
        for chunk in r.iter_content(64 * 1024):
            if chunk:
                search_resp += chunk
                self._update_progress(prog_from, prog_to, len(search_resp), total_size)

        return r, search_resp

    def _do_search_request(self, request_params):
        params = request_params.copy()
        if "apikey" not in params:
            params["apikey"] = self._api_key

        censored_params = params.copy()
        censored_key = censored_params['apikey']
        censored_params['apikey'] = "{}{}{}".format(censored_key[0:2], "*" * 26, censored_key[-4:])
        log.info(f"Making a request to Jackett using params {censored_params}")

        search_resp, content = self._get_with_progress("all/results/torznab", params=params)
        if search_resp.status_code != httplib.OK:
            notify(translation(32700).format(search_resp.reason), image=get_icon_path())
            log.error(f"Jackett returned {search_resp.reason}")
            return []

        err = self.get_error(content)
        if err is not None:
            notify(translation(32700).format(err["description"]), image=get_icon_path())
            log.error(f"got code {err['code']}: {err['description']}")
            return []

        log.info("Jackett returned response")
        log.debug("===============================")
        log.debug(content)
        log.debug("===============================")

        return self._parse_items(content)

    def _parse_items(self, resp_content):
        results = []
        xml = ET.ElementTree(ET.fromstring(resp_content))
        items = xml.getroot().findall("channel/item")
        log.info(f"Found {len(items)} items from response")
        for item in items:
            result = self._parse_item(item)
            if result is not None:
                results.append(result)

        return results

    #  if we didn't get a magnet uri, attempt to resolve the magnet uri.
    #  todo for some reason Elementum cannot resolve the link that gets proxied through Jackett.
    #  So we will resolve it manually for Elementum for now.
    #  In actuality, this should be fixed within Elementum
    def async_magnet_resolve(self, results):
        size = len(results)
        prog_from, prog_to = 25, 90
        self.p_dialog.update(prog_from, message=translation(32751).format(size))

        failed, count = 0, 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=os.cpu_count() * 10) as executor:
            future_to_magnet = {executor.submit(torrent.get_magnet, res["uri"]): res for res in results}
            for future in concurrent.futures.as_completed(future_to_magnet):
                count += 1
                self._update_progress(prog_from, prog_to, count, size)
                res = future_to_magnet[future]
                try:
                    magnet = future.result()
                except Exception as exc:
                    log.warning('%r generated an exception: %s', res, exc)
                    failed += 1
                else:
                    if not magnet:
                        continue
                    log.debug(f"torrent: {res['name']} magnet uri {res['uri']} overridden by {magnet}")
                    res["uri"] = magnet
                    if not res["info_hash"]:
                        res["info_hash"] = torrent.get_info_hash(res['uri'])

        log.warning(f"Failed to resolve {failed} magnet links")
        return results

    def _update_progress(self, pfrom, pto, current, total):
        if not self.p_dialog:
            return

        self.p_dialog.update(int((pfrom + (pto - pfrom) * (current / total)) // 1))

    def _parse_item(self, item):
        result = {
            "name": None,
            "provider": "Unknown",
            "size": "Unknown",
            "uri": None,
            "seeds": "0",
            "peers": "0",
            "info_hash": "",
            "language": None,

            # todo would be nice to assign correct icons but that can be very time consuming due to the number
            #  of indexers in Jackett
            "icon": get_icon_path(),

            "_size_bytes": -1
        }

        for ref in item:
            tag = ref.tag
            attrib = ref.attrib
            if tag == "{" + self._torznab_ns + "}attr":
                val = attrib["value"]
                if "name" in attrib and "value" in attrib and attrib["name"] and val and \
                        attrib["name"] in self._torznab_elementum_mappings["torznab_attrs"]:
                    json = self._torznab_elementum_mappings["torznab_attrs"][attrib["name"]]
                    result[json] = val
                continue

            if ref.tag in self._torznab_elementum_mappings["tags"] and ref.text is not None:
                json = self._torznab_elementum_mappings["tags"][ref.tag]
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

        # if not result["info_hash"]:
        #     result["info_hash"] = torrent.get_info_hash(result['uri'])

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
