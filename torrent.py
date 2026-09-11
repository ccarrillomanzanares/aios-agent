"""Torrent client for AIOS — search, download and play media, driven by the agent.

Stack (installed with sven, official Arch repos only):
  transmission-daemon   BitTorrent engine (headless, local RPC on 127.0.0.1:9091)
  transmission-remote   CLI control of the daemon
  aria2c                HTTP/FTP/magnet downloads for plain documents
  mpv                   media player (video/audio; ffmpeg does the decoding)

Search indexers (plain HTTPS JSON, no extra daemon — keeps the distro lean):
  apibay.org (The Pirate Bay API)  and  torrents-csv.com
Add more indexers in the INDEXERS list below; each one returns the same shape.

Config (key = value):
  /etc/aios-torrent.conf   system defaults
  ~/.aios/torrent.conf     user overrides
"""

import json
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------- constants

RPC_URL = "http://127.0.0.1:9091/transmission/rpc"
UA = "Mozilla/5.0 (X11; Linux x86_64) AIOS/1.0"
SYSTEM_CONF = Path("/etc/aios-torrent.conf")
USER_CONF = Path.home() / ".aios" / "torrent.conf"
CACHE_DIR = Path.home() / ".cache" / "aios-torrent"
LAST_SEARCH = CACHE_DIR / "last_search.json"
MPV_LOG = Path("/tmp/aios-mpv.log")

DEFAULTS = {
    "download_dir": str(Path.home() / "Downloads"),
    "player": "mpv",
    "search_limit": "8",
    "rpc_user": "",
    "rpc_password": "",
    "trackers": ",".join([
        "udp://tracker.opentrackr.org:1337/announce",
        "udp://open.demonii.com:1337/announce",
        "udp://tracker.torrent.eu.org:451/announce",
        "udp://exodus.desync.com:6969/announce",
    ]),
}

# apibay category ids: 0 all, 201/207 movies, 205/208 TV, 101 music, 601 software
VIDEO_CATS = ["207", "201", "205", "208"]


# ---------------------------------------------------------------- config

def config():
    """Merged config: code defaults < /etc/aios-torrent.conf < ~/.aios/torrent.conf."""
    cfg = dict(DEFAULTS)
    for path in (SYSTEM_CONF, USER_CONF):
        try:
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.split("#", 1)[0].strip()
                if not line or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip()
        except FileNotFoundError:
            continue
        except Exception:
            continue
    return cfg


# ---------------------------------------------------------------- helpers

def human_size(n):
    try:
        n = float(n)
    except (TypeError, ValueError):
        return "?"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.2f} {unit}"
        n /= 1024


def magnet_for(info_hash, name, trackers):
    """Build a magnet link.

    NOTE: Transmission 4.1.3 does NOT url-decode the xt value — a percent-encoded
    'urn%3Abtih%3A<hash>' is rejected with "unrecognized info". The xt value must
    therefore be emitted verbatim (raw colons); only dn/tr are encoded.
    """
    ih = (info_hash or "").lower()
    parts = [f"xt=urn:btih:{ih}", "dn=" + urllib.parse.quote(name)]
    for t in trackers.split(","):
        t = t.strip()
        if t:
            parts.append("tr=" + urllib.parse.quote(t))
    return "magnet:?" + "&".join(parts)


def _get(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _cache_search(results):
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        LAST_SEARCH.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception:
        pass


def last_results():
    try:
        return json.loads(LAST_SEARCH.read_text(encoding="utf-8"))
    except Exception:
        return []


# ---------------------------------------------------------------- indexers

def _search_apibay(query, cats, limit):
    out = []
    for cat in cats:
        url = "https://apibay.org/q.php?q=%s&cat=%s" % (urllib.parse.quote(query), cat)
        try:
            data = _get(url)
        except Exception:
            continue
        if not isinstance(data, list):
            continue
        for it in data:
            if not it.get("info_hash") or it.get("info_hash") == "0000000000000000000000000000000000000000":
                continue
            out.append({
                "title": it.get("name", ""),
                "info_hash": it["info_hash"],
                "size_bytes": int(it.get("size") or 0),
                "seeders": int(it.get("seeders") or 0),
                "leechers": int(it.get("leechers") or 0),
                "added": int(it.get("added") or 0),
                "category": it.get("category", ""),
                "source": "apibay",
            })
    return out


def _search_torrents_csv(query, limit):
    out = []
    try:
        data = _get("https://torrents-csv.com/service/search?q=%s&size=%d"
                    % (urllib.parse.quote(query), max(limit, 10)))
    except Exception:
        return out
    for it in (data.get("torrents") or []):
        ih = it.get("infohash") or ""
        if not ih:
            continue
        out.append({
            "title": it.get("name", ""),
            "info_hash": ih,
            "size_bytes": int(it.get("size_bytes") or 0),
            "seeders": int(it.get("seeders") or 0),
            "leechers": int(it.get("leechers") or 0),
            "added": int(it.get("created_unix") or 0),
            "category": "",
            "source": "torrents-csv",
        })
    return out


INDEXERS = [_search_apibay, _search_torrents_csv]


# ---------------------------------------------------------------- search

def search(query, category="video", limit=8):
    """Search torrents by free text. category: 'video' (movies/TV first) or 'all'."""
    cfg = config()
    limit = _as_int(limit) or _as_int(cfg["search_limit"]) or 8
    # Small local models often send stray casing/spacing — normalise so neither
    # the indexer query nor the apibay category lookup silently misses.
    category = str(category or "video").strip().lower()
    cats = VIDEO_CATS + ["0"] if category in ("video", "movies", "all") else [category]

    seen, items = set(), []
    for fn in INDEXERS:
        if fn is _search_apibay:
            found = fn(query, cats, limit)
        else:
            found = fn(query, limit)
        for it in found:
            key = it["info_hash"].lower()
            if key in seen:
                continue
            seen.add(key)
            items.append(it)

    def rank(it):
        # seeders dominate; a release with an exact title match gets a nudge
        title = it["title"].lower()
        exact = 1 if all(w in title for w in query.lower().split()[:3]) else 0
        return (it["seeders"], exact, it["size_bytes"])

    items.sort(key=rank, reverse=True)
    # Drop dead torrents (0 seeders) when there is anything alive: a release with
    # no seeders never downloads, and offering it first wastes the user's time.
    alive = [it for it in items if it["seeders"] > 0]
    if alive:
        items = alive
    items = items[:limit]

    trackers = cfg["trackers"]
    results = []
    for n, it in enumerate(items, 1):
        results.append({
            "n": n,
            "title": it["title"][:90],
            "size": human_size(it["size_bytes"]),
            "size_bytes": it["size_bytes"],
            "seeders": it["seeders"],
            "leechers": it["leechers"],
            "source": it["source"],
            "category": it["category"],
            "magnet": magnet_for(it["info_hash"], it["title"][:80], trackers),
        })
    _cache_search(results)
    return results


# ---------------------------------------------------------------- RPC

_session_id = None


def _rpc(method, args=None, timeout=25):
    global _session_id
    cfg = config()
    body = json.dumps({"method": method, "arguments": args or {}}).encode()
    headers = {"Content-Type": "application/json"}
    if _session_id:
        headers["X-Transmission-Session-Id"] = _session_id
    if cfg.get("rpc_user"):
        import base64
        tok = base64.b64encode(f"{cfg['rpc_user']}:{cfg.get('rpc_password','')}".encode()).decode()
        headers["Authorization"] = "Basic " + tok
    last = None
    for _ in range(3):
        req = urllib.request.Request(RPC_URL, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            if e.code == 409:  # session id handshake
                _session_id = e.headers.get("X-Transmission-Session-Id")
                headers["X-Transmission-Session-Id"] = _session_id
                last = e
                continue
            raise
        except Exception as e:
            last = e
            break
    raise RuntimeError(f"transmission RPC unreachable: {last}")


def daemon_running():
    try:
        _rpc("session-get", timeout=5)
        return True
    except Exception:
        return False


def _expand(p):
    return os.path.expanduser(str(p or ""))


def ensure_daemon():
    """Start the BitTorrent daemon if it is not answering. Returns a status string.

    AIOS runs this as the desktop user, which on the INSTALLED system has neither
    passwordless sudo nor an active polkit — so `sudo -n systemctl start` and a
    plain `systemctl start` both fail with "Access denied". A userspace daemon
    needs no root at all (the RPC port 9091 and the peer port 51413 are >1024, and
    the config/download dirs live in $HOME), so that is the primary path; systemd
    is only a fallback (works on the live ISO / for an admin who enables the unit).
    """
    if daemon_running():
        return "already running"
    cfg = config()
    dl = _expand(cfg["download_dir"])
    try:
        Path(dl).mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    conf_dir = Path.home() / ".config" / "transmission-daemon"

    # --- primary: userspace daemon, owned by the user who will watch the media ---
    try:
        conf_dir.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(
            [shutil.which("transmission-daemon") or "transmission-daemon",
             "-f", "--log-level=error",
             "--config-dir", str(conf_dir),
             "--download-dir", dl,
             "--allowed", "127.0.0.1,::1"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL, start_new_session=True)
        for _ in range(24):
            if daemon_running():
                return "started (user)"
            time.sleep(0.5)
    except Exception as e:
        first_err = f"userspace launch: {e}"
    else:
        first_err = "userspace daemon did not answer on 127.0.0.1:9091"

    # --- fallback: systemd (live ISO has passwordless sudo; admins may enable it) ---
    errs = [first_err]
    for cmd in (["sudo", "-n", "systemctl", "start", "transmission-daemon"],
                ["systemctl", "start", "transmission-daemon"]):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
        except Exception as e:
            errs.append(f"{cmd[0]}: {e}")
            continue
        if r.returncode == 0:
            for _ in range(20):
                if daemon_running():
                    return "started (systemd)"
                time.sleep(0.5)
            errs.append("systemctl returned 0 but RPC is not answering")
        else:
            errs.append((r.stderr or r.stdout or "").strip()[:200])
    return "could not start transmission-daemon: " + " | ".join(errs)


# ---------------------------------------------------------------- downloads

def download(target, name=None):
    """Add a magnet link, a .torrent URL or a search index (1..N).

    Called straight from the model, so anything can arrive: an int, a string, a
    magnet pasted whole, or a 40-hex infohash. All of it is accepted.
    """
    if target is None:
        return {"error": "no magnet or url given"}
    if isinstance(target, (int, float)):
        target = str(int(target))
    target = str(target).strip()
    if not target:
        return {"error": "no magnet or url given"}
    if target.isdigit():
        cached = last_results()
        n = int(target)
        if not (1 <= n <= len(cached)):
            return {"error": f"index {n} out of range (last search had {len(cached)} results)"}
        target = cached[n - 1]["magnet"]
        name = cached[n - 1]["title"]
    elif re.fullmatch(r"[0-9a-fA-F]{40}", target):
        # a bare infohash: models often strip the magnet wrapper
        target = magnet_for(target, name or "", config()["trackers"])
    elif not (target.startswith("magnet:") or target.startswith("http")
              or target.startswith("https") or target.startswith("ftp")):
        return {"error": f"not a magnet link, .torrent url or search number: {target[:60]!r}"}

    ensure_daemon()
    res = _rpc("torrent-add", {"filename": target, "paused": False})
    out = res.get("arguments", {})
    added = out.get("torrent-added") or out.get("torrent-duplicate")
    if isinstance(added, dict):
        return {"added": added.get("name") or name, "id": added.get("id"),
                "duplicate": bool(out.get("torrent-duplicate")),
                "download_dir": _expand(config()["download_dir"])}
    return {"error": res.get("result", "unknown error"), "raw": out}


def _torrent_fields():
    return ["id", "name", "status", "percentDone", "totalSize", "sizeWhenDone",
            "leftUntilDone", "rateDownload", "rateUpload", "eta", "uploadRatio",
            "seeders", "peersConnected", "downloadDir", "error", "errorString",
            "haveValid", "isFinished", "doneDate", "addedDate"]


def status(torrent_id=None, timeout=25):
    """Status of one torrent (id) or all of them."""
    ensure_daemon()
    torrent_id = _as_int(torrent_id)
    args = {"fields": _torrent_fields()}
    if torrent_id is not None:
        args["ids"] = [torrent_id]
    res = _rpc("torrent-get", args, timeout=timeout)
    out = []
    for t in res.get("arguments", {}).get("torrents", []):
        done = float(t.get("percentDone") or 0)
        st = {
            "id": t.get("id"),
            "name": t.get("name"),
            "percent": round(done * 100, 1),
            "status": _status_name(t.get("status")),
            "size": human_size(t.get("totalSize")),
            "downloaded": human_size(t.get("haveValid")),
            "down_speed": human_size(t.get("rateDownload")) + "/s",
            "up_speed": human_size(t.get("rateUpload")) + "/s",
            "eta": _eta(t.get("eta")),
            "peers": t.get("peersConnected"),
            "seeders": t.get("seeders"),
            "dir": _expand(t.get("downloadDir")),
            # isFinished only flips once the session has completed the torrent;
            # data-wise "haveValid == sizeWhenDone" is the honest answer, which
            # matters for playback (a 100% torrent plays even while seeding).
            "finished": bool(t.get("isFinished")) or bool(t.get("haveValid")) and
                        bool(t.get("sizeWhenDone")) and t.get("haveValid") >= t.get("sizeWhenDone"),
        }
        if t.get("error"):
            st["error"] = t.get("errorString") or t.get("error")
        out.append(st)
    return out


def _status_name(code):
    return {0: "stopped", 1: "check queued", 2: "checking", 3: "download queued",
            4: "downloading", 5: "seed queued", 6: "seeding"}.get(code, str(code))


def _eta(sec):
    try:
        sec = int(sec)
    except (TypeError, ValueError):
        return "?"
    if sec < 0 or sec > 86400 * 30:
        return "?"
    h, m = divmod(sec // 60, 60)
    return f"{h}h{m:02d}m" if h else f"{m}m{sec % 60:02d}s"


def control(action, torrent_id):
    """action: start | stop | remove | remove-data | verify."""
    ensure_daemon()
    tid = [_as_int(torrent_id)]
    if tid == [None]:
        return {"error": f"invalid torrent id: {torrent_id!r}"}
    if action in ("start", "stop", "verify"):
        res = _rpc("torrent-" + action, {"ids": tid})
    elif action in ("remove", "remove-data"):
        res = _rpc("torrent-remove", {"ids": tid, "delete-local-data": action == "remove-data"})
    else:
        return {"error": f"unknown action '{action}' (use start|stop|remove|remove-data|verify)"}
    return {"ok": res.get("result") == "success", "result": res.get("result")}


# ---------------------------------------------------------------- playback

VIDEO_EXT = {".mp4", ".mkv", ".avi", ".webm", ".m4v", ".mov", ".mpg", ".mpeg",
             ".wmv", ".flv", ".ts", ".m2ts", ".ogv", ".3gp"}
AUDIO_EXT = {".mp3", ".flac", ".ogg", ".opus", ".m4a", ".aac", ".wav", ".wma"}


def newest_media(within_minutes=None):
    """Newest video/audio file under the download dir (optionally recent ones only)."""
    root = Path(config()["download_dir"]).expanduser()
    best, best_m = None, -1
    if not root.is_dir():
        return None
    cutoff = time.time() - within_minutes * 60 if within_minutes else 0
    for p in root.rglob("*"):
        try:
            if not p.is_file() or p.name.startswith("."):
                continue
            if _media_ext(p) is None:
                continue
            m = p.stat().st_mtime
            if m >= cutoff and m > best_m:
                best, best_m = p, m
        except OSError:
            continue
    return best


def _as_bool(v, default=True):
    """Coerce a tool argument to bool.

    Models are inconsistent: the same field arrives as true/1/"true"/"yes" from one
    and as "false"/"" from another. A plain bool("false") is True, which would turn
    fullscreen off into fullscreen on — hence the explicit parsing.
    """
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    s = str(v).strip().lower()
    if s in ("false", "0", "no", "off", "n", ""):
        return False
    if s in ("true", "1", "yes", "on", "y"):
        return True
    return default


def _as_int(v):
    """Coerce a tool argument to int, tolerating '3', 3.0, ' 3 ' — or None."""
    if v is None or v == "":
        return None
    try:
        return int(float(str(v).strip()))
    except (TypeError, ValueError):
        return None


def play(path=None, fullscreen=True, torrent_id=None):
    """Play a file with mpv.

    Works with a finished torrent AND with a partially downloaded one (mpv plays
    partial files); the result reports the torrent's completion so the agent can
    tell the user what to expect. With no path/id: newest media file on disk.
    """
    fullscreen = _as_bool(fullscreen, True)
    torrent_id = _as_int(torrent_id)
    cfg = config()
    player = shutil.which(cfg["player"]) or cfg["player"]
    info = {}

    if path and Path(path).exists():
        target = Path(path)
    elif torrent_id not in (None, ""):
        found = _media_of_torrent(torrent_id)
        if not found:
            return {"error": f"no media file for torrent {torrent_id}",
                    "hint": "the torrent may have no video/audio files, or the download "
                            "has not produced any file yet — check torrent_status"}
        target, info = found
    else:
        target = newest_media()
        if target is None:
            return {"error": "no media file found",
                    "hint": f"looked in {_expand(cfg['download_dir'])} — check torrent_status first"}

    if target is None or not Path(target).exists():
        return {"error": "media file is not on disk"}

    # Only one player at a time: without this, asking for a second film leaves the
    # first mpv running and the user hears two soundtracks at once.
    try:
        subprocess.run(["pkill", "-f", r"mpv .*--really-quiet"], timeout=10,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.4)
    except Exception:
        pass

    # Audio: keep mpv's default (auto). In AIOS the desktop session runs PipeWire
    # (wireplumber + pipewire sockets under /run/user/1000), so mpv finds it via
    # XDG_RUNTIME_DIR — which the agent's own environment already provides. Forcing
    # --ao=alsa here would BYPASS PipeWire and fail on a busy device.
    args = [player, "--really-quiet", "--force-window=yes", "--keep-open=no",
            "--save-position-on-quit=yes", "--no-terminal"]
    if fullscreen:
        args.append("--fullscreen")
    args.append(str(target))
    try:
        with open(MPV_LOG, "ab") as log:
            subprocess.Popen(args, stdout=log, stderr=log, stdin=subprocess.DEVNULL,
                             start_new_session=True)
    except FileNotFoundError:
        return {"error": f"player not found: {player}"}
    out = {"playing": str(target), "player": Path(player).name, "fullscreen": bool(fullscreen)}
    out.update(info)
    return out


def _media_ext(p):
    """Video/audio extension of a path, tolerating download placeholders.

    Transmission writes "Big Buck Bunny.mp4.part" while downloading, so the last
    suffix is '.part' and the real media type is one suffix further in.
    """
    suffixes = [s.lower() for s in p.suffixes]
    if p.suffix.lower() == ".part" and len(suffixes) > 1:
        suffixes = suffixes[:-1]
    for s in reversed(suffixes):
        if s in VIDEO_EXT | AUDIO_EXT:
            return s
    return None


def _media_of_torrent(tid):
    """(path, info) of the media file of a torrent, if any is already on disk."""
    st = status(tid)
    if not st:
        return None
    t = st[0]
    root = Path(t["dir"]).expanduser()
    name = t.get("name") or ""
    cands = []
    try:
        for p in root.rglob("*"):
            try:
                if not p.is_file():
                    continue
                if _media_ext(p) is None:
                    continue
                # multi-file torrents live in a dir named after the torrent;
                # single-file ones carry the torrent's name in the filename
                if name[:30] and name[:30].lower() not in str(p).lower():
                    continue
                cands.append((p.stat().st_mtime, p))
            except OSError:
                continue
    except OSError:
        return None
    if not cands:
        return None
    path = max(cands)[1]
    return path, {"torrent_id": t["id"], "torrent_name": t["name"],
                  "downloaded_percent": t["percent"], "complete": bool(t["finished"]),
                  "partial": path.suffix.lower() == ".part"}


def _path_of_torrent(tid):
    """Backward-compatible helper: path only (None if nothing playable yet)."""
    found = _media_of_torrent(tid)
    return found[0] if found else None


# ---------------------------------------------------------------- aria2 (documents)

def fetch(url, out_dir=None):
    """Download a plain URL (http/https/ftp/magnet) with aria2c — documents, not media."""
    cfg = config()
    out = Path(out_dir or cfg["download_dir"]).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["aria2c", "--console-log-level=warn", "--summary-interval=0",
                        "-c", "-x", "4", "-s", "4", "-d", str(out), url],
                       capture_output=True, text=True, timeout=1800)
    if r.returncode != 0 and "download completed" not in (r.stdout or "").lower():
        return {"ok": False, "error": (r.stderr or r.stdout or "").strip()[-400:]}
    return {"ok": True, "dir": str(out)}
