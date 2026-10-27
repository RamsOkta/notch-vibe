import re
import urllib.parse
import requests

_LYRICS_CACHE = {}


def parse_lrc(lrc_text: str):
    """Menguraikan teks LRC menjadi list tuple (detik_float, teks_lirik)."""
    pattern = re.compile(r"\[(\d+):(\d+(?:\.\d+)?)\](.*)")
    parsed = []
    for line in lrc_text.splitlines():
        match = pattern.match(line.strip())
        if match:
            minutes = int(match.group(1))
            seconds = float(match.group(2))
            text = match.group(3).strip()
            # Bersihkan spasi berlebih
            text = re.sub(r"\s+", " ", text)
            if text:
                parsed.append((minutes * 60.0 + seconds, text))
    parsed.sort(key=lambda x: x[0])
    return parsed


def fetch_lyrics_from_lrclib(clean_title: str, clean_artist: str, raw_title: str, duration: float = 0.0):
    """
    Mencari lirik lagu dari API LRCLIB dengan verifikasi durasi agar 100% pas dan tersinkron.
    Mengembalikan: (parsed_lyrics, sync_type, matched_duration)
    """
    cache_key = f"{clean_artist.lower()}|{clean_title.lower()}"
    if cache_key in _LYRICS_CACHE:
        return _LYRICS_CACHE[cache_key]

    headers = {"User-Agent": "NusaMacNotch/2.0"}

    # 1. Coba pencarian presisi via /api/get (jika ada durasi lagu)
    if duration > 10.0 and clean_title:
        try:
            params = {
                "track_name": clean_title,
                "artist_name": clean_artist if clean_artist else "",
                "duration": int(round(duration)),
            }
            url = f"https://lrclib.net/api/get?{urllib.parse.urlencode(params)}"
            resp = requests.get(url, timeout=3.5, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("syncedLyrics"):
                    parsed = parse_lrc(data["syncedLyrics"])
                    if parsed:
                        res = (parsed, "Synced", float(data.get("duration") or duration))
                        _LYRICS_CACHE[cache_key] = res
                        return res
        except Exception:
            pass

    # 2. Coba pencarian fleksibel via /api/search dan cocokkan yang durasinya paling mendekati
    queries = []
    if clean_artist and clean_artist.lower() not in clean_title.lower():
        queries.append(f"{clean_artist} {clean_title}")
    queries.append(clean_title)
    if raw_title != clean_title:
        queries.append(re.sub(r"^\(\d+\)\s*", "", raw_title))

    for q in queries:
        q = q.strip()
        if not q:
            continue
        try:
            url = f"https://lrclib.net/api/search?{urllib.parse.urlencode({'q': q})}"
            resp = requests.get(url, timeout=4.0, headers=headers)
            if resp.status_code == 200:
                items = resp.json()
                if not items:
                    continue

                # Filter hanya yang memiliki syncedLyrics
                synced_candidates = [it for it in items if it.get("syncedLyrics")]
                if synced_candidates:
                    # Urutkan berdasarkan selisih durasi terkecil agar versi lagu pas
                    if duration > 10.0:
                        synced_candidates.sort(
                            key=lambda x: abs(float(x.get("duration") or 0.0) - duration)
                        )
                    best = synced_candidates[0]
                    parsed = parse_lrc(best["syncedLyrics"])
                    if parsed:
                        res = (parsed, "Synced", float(best.get("duration") or duration))
                        _LYRICS_CACHE[cache_key] = res
                        return res

                # Jika tidak ada synced, ambil plain lyrics sebagai fallback
                plain_candidates = [it for it in items if it.get("plainLyrics")]
                if plain_candidates:
                    plain_text = plain_candidates[0]["plainLyrics"]
                    lines = [
                        (i * 3.8, l.strip())
                        for i, l in enumerate(plain_text.splitlines())
                        if l.strip()
                    ]
                    if lines:
                        res = (lines, "Plain", float(plain_candidates[0].get("duration") or duration))
                        _LYRICS_CACHE[cache_key] = res
                        return res
        except Exception:
            pass

    return None, None, 0.0
