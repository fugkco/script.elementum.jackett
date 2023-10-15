import base64
import io
from http import client as httplib

import requests
from torf import Torrent, Magnet

from logger import log

session = requests.Session()
session.headers['User-Agent'] = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 ' \
                                '(KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36'


def get_magnet(original_uri):
    magnet_prefix = 'magnet:'
    uri = original_uri

    while True:
        if len(uri) >= len(magnet_prefix) and uri[0:7] == magnet_prefix:
            return uri
        try:
            response = session.get(uri, allow_redirects=False, timeout=10)
        except requests.exceptions.Timeout as e:
            log.warning(f"Timeout while resolving torrent {uri}")
            break

        if response.is_redirect:
            uri = response.headers['Location']
        elif response.status_code == httplib.OK and response.headers.get('Content-Type') == 'application/x-bittorrent':
            torrent = Torrent.read_stream(io.BytesIO(response.content))
            return str(torrent.magnet())
        else:
            log.warning(f"Could not get final redirect location for URI {original_uri}. "
                        f"Response was: {response.status_code} {response.reason}")
            log.debug(f"Response for failed redirect {original_uri} is")
            log.debug("=" * 50)
            for (h, k) in list(response.headers.items()):
                log.debug(f"{h}: {k}")
            log.debug("")
            log.debug(base64.standard_b64encode(response.content))
            log.debug("=" * 50)
            break

    return None


def get_info_hash(magnet):
    return Magnet.from_string(magnet).infohash
