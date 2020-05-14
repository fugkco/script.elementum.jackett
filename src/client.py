#!/usr/bin/env python3.6
# coding=utf-8
import httplib
import xml.etree.ElementTree as ET
from urlparse import urljoin

from elementum.provider import log
from requests_toolbelt import sessions

from utils import notify, translation, get_icon_path, human_size, get_resolution, get_release_type


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
            log.error("Jackett return {}", caps_resp.reason)
            return

        err = self.get_error(caps_resp.content)
        if err is not None:
            notify(translation(32700).format(err["description"]), image=get_icon_path())
            log.error("got code {}: {}", err["code"], err["description"])
            return

        xml = ET.ElementTree(ET.fromstring(caps_resp.content)).getroot()

        self._caps["limits"] = xml.find("limits").attrib

        self._caps["search_tags"] = {}
        for type_tag in xml.findall('searching/*'):
            self._caps["search_tags"][type_tag.tag] = {
                "enabled": type_tag.attrib["available"] == "yes",
                "params": [p for p in type_tag.attrib['supportedParams'].split(",") if p],
            }

        # todo maybe categories are needed?

    def search_movie(self, title, imdb_id):
        if "search_tags" not in self._caps:
            notify(translation(32701), image=get_icon_path())
            return []

        movie_search_caps = self._caps["search_tags"]['movie-search']
        if not movie_search_caps['enabled']:
            notify(translation(32702).format("movie"), image=get_icon_path())
            log.warning("Jackett has no movie capabilities, please add a indexer that has movie capabilities. "
                        "Falling back to query search...")
            return self.search_query(title)

        # todo what values are possible for imdb_id?
        movie_params = movie_search_caps["params"]
        request_params = {
            "t": "tvsearch",
            "apikey": self._api_key
        }
        if imdb_id and 'imdbid' in movie_params:
            request_params["imdbid"] = imdb_id
        else:
            request_params["q"] = title

        return self._do_search_request(request_params)

    def search_shows(self, title, season=None, episode=None, imdb_id=None):
        if "search_tags" not in self._caps:
            notify(translation(32701), image=get_icon_path())
            return []

        tv_search_caps = self._caps["search_tags"]['tv-search']
        if not tv_search_caps['enabled']:
            notify(translation(32702).format("show"), image=get_icon_path())  # todo
            log.warning("Jackett has no tvsearch capabilities, please add a indexer that has tvsearch capabilities. "
                        "Falling back to query search...")

            if bool(season):
                title = title + " S{:0>2}".format(season)
                if bool(episode):
                    title = title + "E{:0>2}".format(episode)

            return self.search_query(title)

        # todo what values are possible for imdb_id?
        tv_params = tv_search_caps["params"]
        request_params = {
            "t": "tvsearch",
            "apikey": self._api_key
        }
        if imdb_id and 'imdbid' in tv_params:
            request_params["imdbid"] = imdb_id
        else:
            request_params["q"] = title
            if bool(season) and 'season' in tv_params:
                request_params["season"] = season
            if bool(episode) and 'ep' in tv_params:
                request_params["ep"] = episode

        return self._do_search_request(request_params)

    def search_season(self, title, season, imdb_id):
        return self.search_shows(title, season=season, imdb_id=imdb_id)

    def search_episode(self, title, season, episode, imdb_id):
        return self.search_shows(title, season=season, episode=episode, imdb_id=imdb_id)

    def search_query(self, query):
        request_params = {
            "t": "tvsearch",
            "apikey": self._api_key,
            "q": query
        }

        return self._do_search_request(request_params)

    def _do_search_request(self, request_params):
        search_resp = self._session.get("all/results/torznab", params=request_params)
        if search_resp.status_code != httplib.OK:
            log.error("Jackett return {}", search_resp.reason)
            return

        return self._parse_items(search_resp.content)

    def _parse_items(self, resp_content):
        results = []
        xml = ET.ElementTree(ET.fromstring(resp_content))
        for item in xml.getroot().findall("channel/item"):
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
            "icon": "icons/1337x.png",  # todo

            "_size_bytes": -1
        }

        for ref in item:
            tag = ref.tag
            attrib = ref.attrib
            if tag == "{" + self._torznab_ns + "}attr":
                if "name" in attrib and "value" in attrib and attrib["name"] and attrib["value"] and \
                        attrib["name"] in self._torznab_elementum_mappings["torznab_attrs"]:
                    json = self._torznab_elementum_mappings["torznab_attrs"][attrib["name"]]
                    result[json] = attrib["value"]
                continue

            if ref.tag in self._torznab_elementum_mappings["tags"] and ref.text is not None:
                json = self._torznab_elementum_mappings["tags"][ref.tag]
                result[json] = ref.text.strip()

        if result["name"] is None or result["uri"] is None:
            return None

        # result["name"] = result["name"].decode("utf-8") # might be needed for non-english items
        result["seeds"] = int(result["seeds"])
        result["peers"] = int(result["peers"])
        result["resolution"] = get_resolution(result["name"])
        result["release_type"] = get_release_type(result["name"])

        if result["size"] != "Unknown":
            result["_size_bytes"] = int(result["size"])
            result["size"] = human_size(result["_size_bytes"])

        return result
