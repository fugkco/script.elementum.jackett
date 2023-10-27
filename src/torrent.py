import base64
import io
import aiohttp
import asyncio
import time
from torf import Torrent, Magnet
from http import HTTPStatus

import utils
from logger import log


#  if we didn't get a magnet uri, attempt to resolve the magnet uri.
#  todo for some reason Elementum cannot resolve the link that gets proxied through Jackett.
#  So we will resolve it manually for Elementum for now.
#  In actuality, this should be fixed within Elementum
async def uri_to_magnets_uniq_torrents(torrents, p_dialog_cb=None):
    ret = []
    count = 0
    hash_set = set()
    async with aiohttp.ClientSession() as session:
        session.headers['User-Agent'] = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 ' \
                                        '(KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36'
        tasks = [torrent_uri_to_magnet(session, tor) for tor in torrents]
        total = len(tasks)
        for task in asyncio.as_completed(tasks):
            torrent = await task
            count += 1
            if p_dialog_cb:
                p_dialog_cb(count, total, message=utils.translation(32751).format(count, total))
            if not torrent['uri']:
                continue
            m_hash = get_info_hash(torrent['uri'])
            if not m_hash or m_hash in hash_set:
                continue
            hash_set.add(m_hash)
            ret.append(torrent)
    return ret


async def torrent_uri_to_magnet(session, torrent):
    torrent['uri'] = await get_magnet(session, torrent["uri"])
    return torrent


async def get_magnet(session, original_uri):
    magnet_prefix = 'magnet:'
    redirect_count = -1
    uri = original_uri
    start = time.monotonic()
    while True:
        redirect_count += 1
        if len(uri) >= len(magnet_prefix) and uri[0:7] == magnet_prefix:
            response_time = time.monotonic() - start
            log.debug(f"{response_time:.3f}s redirect-{redirect_count} magnet {uri}")
            return uri
        try:
            async with session.get(uri, allow_redirects=False, timeout=10) as resp:
                if resp.status == HTTPStatus.OK and resp.headers.get(
                        'Content-Type') == 'application/x-bittorrent':
                    data = await resp.read()
                    torrent = Torrent.read_stream(io.BytesIO(data))
                    magnet = str(torrent.magnet())
                    response_time = time.monotonic() - start
                    log.debug(f"{response_time:.3f}s magnet {magnet}")
                    return magnet
                elif resp.status in (301, 302, 303, 307, 308):
                    uri = resp.headers['Location']
                else:
                    log.warning(f"Could not get final redirect location for URI {original_uri}. "
                                f"Response was: {resp.status} {resp.reason}")
                    log.debug(f"Response for failed redirect {original_uri} is")
                    log.debug("=" * 50)
                    for (h, k) in list(resp.headers.items()):
                        log.debug(f"{h}: {k}")
                    log.debug("")
                    log.debug(base64.standard_b64encode(resp.content))
                    log.debug("=" * 50)
                    break
        except Exception as e:
            log.warning(f"Can't resolve uri {uri} torrent: {e}")
            break
    return None


def get_info_hash(magnet):
    return Magnet.from_string(magnet).infohash
