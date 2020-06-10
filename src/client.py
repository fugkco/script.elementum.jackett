#!/usr/bin/env python3.6
# coding=utf-8
import base64
import httplib
import re
import xml.etree.ElementTree as ET
from urlparse import urljoin
from xml.etree import ElementTree

import requests
from elementum.provider import log
from requests_toolbelt import sessions
from torrentool.torrent import Torrent

from src import utils
from utils import notify, translation, get_icon_path, human_size, get_resolution, get_release_type, get_setting, \
    set_setting


# import logging
# log = logging

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

    def __init__(self, host, api_key):
        super(Jackett, self).__init__()
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
            log.error("Jackett return %s", caps_resp.reason)
            set_setting('settings_validated', caps_resp.reason)
            return

        err = self.get_error(caps_resp.content)
        if err is not None:
            notify(translation(32700).format(err["description"]), image=get_icon_path())
            log.error("got code %s: %s", err["code"], err["description"])
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

        log.info("Found capabilities: %s", repr(self._caps))
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
            return self.search_query(title + u' ' + year)

        # todo what values are possible for imdb_id?
        movie_params = movie_search_caps["params"]
        request_params = {
            "t": "movie",
            "apikey": self._api_key
        }

        has_imdb_caps = 'imdbid' in movie_params
        log.debug("movie search; imdb_id=%s, has_imdb_caps=%s", imdb_id, has_imdb_caps)
        if imdb_id and has_imdb_caps:
            request_params["imdbid"] = imdb_id
        else:
            request_params["q"] = title + u' ' + year
            log.debug("searching movie with query=%s", request_params["q"])

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
            "apikey": self._api_key
        }
        has_imdb_caps = 'imdbid' in tv_params
        log.debug("movie search; imdb_id=%s, has_imdb_caps=%s", imdb_id, has_imdb_caps)
        if imdb_id and has_imdb_caps:
            request_params["imdbid"] = imdb_id
        else:
            log.debug("searching tv show with query=%s, season=%s, episode=%s", title, season, episode)
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
        return [
            result for result in results
            if re.search(r'\bS(eason )?' + season_query + r'\b', result['name'], re.IGNORECASE)
        ]

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
            "apikey": self._api_key,
            "q": query
        }

        return self._do_search_request(request_params)

    def _do_search_request(self, request_params):
        censored_params = request_params.copy()
        censored_key = censored_params['apikey']
        censored_params['apikey'] = "{}{}{}".format(censored_key[0:2], "*" * 26, censored_key[-4:])
        log.debug('Making a request to Jackett using params %s', repr(censored_params))

        search_resp = self._session.get("all/results/torznab", params=request_params)
        if search_resp.status_code != httplib.OK:
            notify(translation(32700).format(search_resp.reason), image=get_icon_path())
            log.error("Jackett returned %s", search_resp.reason)
            return []

        err = self.get_error(search_resp.content)
        if err is not None:
            notify(translation(32700).format(err["description"]), image=get_icon_path())
            log.error("got code %s: %s", err["code"], err["description"])
            return []

        log.debug("Jackett returned below response")
        log.debug("===============================")
        log.debug(search_resp.content)
        log.debug("===============================")

        return self._parse_items(search_resp.content)

    def _parse_items(self, resp_content):
        results = []
        xml = ET.ElementTree(ET.fromstring(resp_content))
        items = xml.getroot().findall("channel/item")
        log.info("Found %d items from response", len(items))
        for item in items:
            result = self._parse_item(item)
            if result is not None:
                results.append(result)

        return results

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
                if isinstance(val, str):
                    val = val.decode("utf-8")
                if "name" in attrib and "value" in attrib and attrib["name"] and val and \
                        attrib["name"] in self._torznab_elementum_mappings["torznab_attrs"]:
                    json = self._torznab_elementum_mappings["torznab_attrs"][attrib["name"]]
                    result[json] = val
                continue

            if ref.tag in self._torznab_elementum_mappings["tags"] and ref.text is not None:
                json = self._torznab_elementum_mappings["tags"][ref.tag]
                val = ref.text.strip()

                if isinstance(val, str):
                    val = val.decode("utf-8")

                result[json] = val

        # if we didn't get a magnet uri, attempt to resolve the magnet uri.
        # todo for some reason Elementum cannot resolve the link that gets proxied through Jackett.
        #  So we will resolve it manually for Elementum for now.
        #  In actuality, this should be fixed within Elementum
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
                result["uri"] = get_magnet_from_jackett(jackett_uri)

        if result["name"] is None or result["uri"] is None:
            log.warning("Could not parse item; name = %s; uri = %s", result["name"], result["uri"])
            log.debug("Failed item is: %s", ElementTree.tostring(item, encoding='utf8'))
            return None

        # result["name"] = result["name"].decode("utf-8") # might be needed for non-english items
        result["seeds"] = int(result["seeds"])
        result["peers"] = int(result["peers"])
        resolution = get_resolution(result["name"])
        result["resolution"] = utils.resolutions.keys()[::-1].index(resolution)
        result["_resolution"] = resolution
        result["release_type"] = get_release_type(result["name"])

        if result["size"] != "Unknown":
            result["_size_bytes"] = int(result["size"])
            result["size"] = human_size(result["_size_bytes"])

        return result


def get_magnet_from_jackett(original_uri):
    magnet_prefix = 'magnet:'
    uri = original_uri
    while True:
        if len(uri) >= len(magnet_prefix) and uri[0:7] == magnet_prefix:
            return uri

        response = requests.get(uri, allow_redirects=False)
        if response.is_redirect:
            uri = response.headers['Location']
        elif response.status_code == httplib.OK and response.headers.get('Content-Type') == 'application/x-bittorrent':
            torrent = Torrent.from_string(response.content)
            return torrent.get_magnet(True)
        else:
            log.warning("Could not get final redirect location for URI %s. Response was: %d %s", original_uri,
                        response.status_code, response.reason)
            log.debug("Response for failed redirect %s is", original_uri)
            log.debug("=" * 50)
            [log.debug("%s: %s", h, k) for (h, k) in response.headers.iteritems()]
            log.debug("")
            log.debug("%s", base64.standard_b64encode(response.content))
            log.debug("=" * 50)
            break

    return None
