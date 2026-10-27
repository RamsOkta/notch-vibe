import urllib.parse
import requests

# Cache in-memory untuk menyimpan URL gambar dan data binary gambar
_ARTWORK_URL_CACHE = {}
_IMAGE_BYTES_CACHE = {}


def fetch_artwork_url(title: str, artist: str) -> str:
    """Mencari URL cover art resolusi tinggi (300x300) dari iTunes Search API."""
    key = f"{artist.lower()}|{title.lower()}".strip()
    if key in _ARTWORK_URL_CACHE:
        return _ARTWORK_URL_CACHE[key]

    queries = []
    if artist and artist.lower() not in title.lower():
        queries.append(f"{artist} {title}")
    queries.append(title)

    for q in queries:
        q = q.strip()
        if not q:
            continue
        try:
            url = f"https://itunes.apple.com/search?term={urllib.parse.quote(q)}&entity=song&limit=1"
            resp = requests.get(url, timeout=3.5, headers={"User-Agent": "NusaMacNotch/2.0"})
            if resp.status_code == 200:
                data = resp.json()
                if data.get("results"):
                    art_100 = data["results"][0].get("artworkUrl100", "")
                    if art_100:
                        high_res = art_100.replace("100x100bb", "300x300bb")
                        _ARTWORK_URL_CACHE[key] = high_res
                        return high_res
        except Exception:
            pass

    _ARTWORK_URL_CACHE[key] = ""
    return ""


def download_artwork_bytes(url: str) -> bytes:
    """Mengunduh file gambar binary album artwork."""
    if not url:
        return b""
    if url in _IMAGE_BYTES_CACHE:
        return _IMAGE_BYTES_CACHE[url]

    try:
        resp = requests.get(url, timeout=4.0, headers={"User-Agent": "NusaMacNotch/2.0"})
        if resp.status_code == 200 and resp.content:
            _IMAGE_BYTES_CACHE[url] = resp.content
            return resp.content
    except Exception:
        pass
    return b""
