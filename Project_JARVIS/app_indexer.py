# app_indexer.py
import os
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional, Tuple
import difflib
import time

# ------- Config -------
SCAN_ROOTS = [
    r"C:\Program Files",
    r"C:\Program Files (x86)",
    r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs",
    os.path.expanduser(r"~\AppData\Roaming\Microsoft\Windows\Start Menu\Programs"),
]
INDEX_FILE = "apps_index.json"
MAX_WORKERS = min(6, len(SCAN_ROOTS) or 1)

# ------- Module state -------
APP_ENTRIES: List[Dict[str, str]] = []  # list of {"name": ..., "path": ...}
APP_NAME_TO_PATH: Dict[str, str] = {}   # name -> path


# ------- Utilities -------
def _normalize_name(filename: str) -> str:
    """
    Turn a filename like 'Code.exe' or 'Photoshop 2022.exe' into a
    normalized, searchable, lowercase name: 'visual studio code' or 'photoshop 2022'.
    """
    name = filename.rsplit(".", 1)[0]  # remove extension
    name = name.replace("_", " ").replace("-", " ")
    # Remove common version tags in parentheses or trailing v1.2 etc.
    name = re.sub(r"\(.*?\)", "", name)
    name = re.sub(r"v?\d+(\.\d+)*", "", name)
    name = re.sub(r"\s+", " ", name)
    return name.strip().lower()


# ------- ScanBot -------
class ScanBot:
    def __init__(self, bot_id: int, root_dir: str):
        self.bot_id = bot_id
        self.root_dir = root_dir
        self.results: List[Dict[str, str]] = []

    def run(self):
        '''
        Scans self.root_dir for .exe files and applies heuristics to filter user-facing apps.
        Returns list of entries: {"name": ..., "path": ...}
        '''
        # Tunable constants / heuristics
        EXCLUDE_KEYWORDS = [
            "install", "setup", "update", "updater", "uninstall", "unins", "patch",
            "driver", "service", "msiexec", "helper", "launcher_temp", "temp", "bootstrap",
            "unpacker", "repair", "cleanup", "background", "monitor", "agent", "agentexe"
        ]
        MIN_FILE_SIZE = 50 * 1024  # 50 KB, filter out tiny helpers (tweakable)
        START_MENU_MARKERS = [
            "start menu", "programs", "appdata", "startmenu"
        ]

        if not os.path.exists(self.root_dir):
            print(f"[Bot {self.bot_id}] Skipping missing: {self.root_dir}")
            return self.results

        print(f"[Bot {self.bot_id}] Scanning {self.root_dir} ...")
        start = time.time()

        try:
            for root, dirs, files in os.walk(self.root_dir):
                for fname in files:
                    if not fname.lower().endswith(".exe"):
                        continue

                    full = os.path.join(root, fname)

                    # basic file-size guard (skip tiny files)
                    try:
                        size = os.path.getsize(full)
                    except Exception:
                        size = 0
                    if size > 0 and size < MIN_FILE_SIZE:
                        # tiny helper / DLL-like drop: skip
                        continue

                    base = fname.rsplit(".", 1)[0].lower()

                    # exclude suspicious keywords in filename
                    if any(k in base for k in EXCLUDE_KEYWORDS):
                        continue

                    # derive parent folder name
                    parent = os.path.basename(root).lower()

                    # Accept automatically if this is inside a Start Menu / Programs folder
                    root_l = root.lower()
                    in_start_menu = any(marker in root_l for marker in START_MENU_MARKERS)

                    # Accept if filename matches parent folder (very likely launcher),
                    # or if parent contains the filename (e.g., 'Photoshop' folder containing 'Photoshop.exe')
                    name_matches_parent = (base == parent) or (base in parent) or (parent in base)

                    # If it's in Start Menu (shortcuts area) treat as user-facing app
                    if in_start_menu or name_matches_parent:
                        entry_name = _normalize_name(fname)
                        if entry_name:
                            self.results.append({"name": entry_name, "path": full})
                        continue

                    # If not in start menu and doesn't match parent, perform an additional sanity check:
                    # - file size > 300 KB (likely real app binary), keep it
                    if size >= (300 * 1024):
                        entry_name = _normalize_name(fname)
                        if entry_name:
                            self.results.append({"name": entry_name, "path": full})
                        continue

                    # else: ambiguous small exe in program tree -> skip
                    # (This filters many updater/helper exes inside app folders)
                    continue

        except Exception as e:
            print(f"[Bot {self.bot_id}] Error scanning {self.root_dir}: {e}")

        elapsed = time.time() - start
        print(f"[Bot {self.bot_id}] Done. Found {len(self.results)} candidate exes in {elapsed:.1f}s")
        return self.results



# ------- Index build / save / load -------
def build_index(save: bool = True) -> List[Dict[str, str]]:
    """
    Run parallel scans across SCAN_ROOTS and return the combined list of entries.
    If save=True, writes apps_index.json.
    """
    global APP_ENTRIES, APP_NAME_TO_PATH

    bots = [ScanBot(i, root) for i, root in enumerate(SCAN_ROOTS)]
    all_entries: List[Dict[str, str]] = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(bot.run): bot for bot in bots}
        for fut in as_completed(futures):
            bot = futures[fut]
            try:
                results = fut.result()
                all_entries.extend(results)
            except Exception as e:
                print(f"[Index] Bot {bot.bot_id} failed: {e}")

    # Deduplicate by name -> prefer first discovered path
    dedup: Dict[str, str] = {}
    for e in all_entries:
        name = e["name"]
        path = e["path"]
        if name in dedup:
            # prefer existing or choose shorter path (heuristic)
            if len(path) < len(dedup[name]):
                dedup[name] = path
        else:
            dedup[name] = path

    # Build normalized entries list
    APP_ENTRIES = [{"name": n, "path": p} for n, p in dedup.items()]
    APP_NAME_TO_PATH = dict(dedup)

    if save:
        try:
            with open(INDEX_FILE, "w", encoding="utf-8") as f:
                json.dump({"apps": APP_ENTRIES}, f, indent=2, ensure_ascii=False)
            print(f"[Index] Saved {len(APP_ENTRIES)} apps to {INDEX_FILE}")
        except Exception as e:
            print("[Index] Failed to save index:", e)

    return APP_ENTRIES


def load_index() -> None:
    """Load index from disk into memory. If missing, calls build_index()."""
    global APP_ENTRIES, APP_NAME_TO_PATH
    if APP_ENTRIES:
        return

    if os.path.exists(INDEX_FILE):
        try:
            with open(INDEX_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            apps = data.get("apps", [])
            APP_ENTRIES = apps
            APP_NAME_TO_PATH = {e["name"]: e["path"] for e in apps}
            print(f"[Index] Loaded {len(APP_ENTRIES)} apps from {INDEX_FILE}")
            return
        except Exception as e:
            print("[Index] Failed to load index, will rebuild:", e)

    # fallback: build
    build_index(save=True)


# ------- Search API -------
def _simple_search(query: str) -> Optional[Tuple[str, str]]:
    """
    Try exact and substring matching.
    Returns (name, path) or None.
    """
    query = query.lower().strip()
    # Exact
    if query in APP_NAME_TO_PATH:
        return query, APP_NAME_TO_PATH[query]

    # Substring match: check if query inside name
    for name, path in APP_NAME_TO_PATH.items():
        if query in name:
            return name, path

    return None


def find_app(query: str, fuzzy_cutoff: float = 0.6) -> Optional[Tuple[str, str]]:
    """
    Find best matching app for a query.
    Returns (display_name, path) or None.
    """
    if not query:
        return None

    load_index()

    q = query.lower().strip()
    # quick cleanup: remove leading "open ", etc if present
    q = re.sub(r"^(open|launch|start)\s+", "", q)

    # 1) simple match
    res = _simple_search(q)
    if res:
        return res

    # 2) fuzzy match using difflib on the available names
    names = list(APP_NAME_TO_PATH.keys())
    if not names:
        return None

    matches = difflib.get_close_matches(q, names, n=3, cutoff=fuzzy_cutoff)
    if matches:
        best = matches[0]
        return best, APP_NAME_TO_PATH[best]

    # 3) fallback: try to match by token overlap (looser)
    q_tokens = set(q.split())
    best_name = None
    best_score = 0
    for name in names:
        name_tokens = set(name.split())
        score = len(q_tokens & name_tokens)
        if score > best_score:
            best_score = score
            best_name = name
    if best_score > 0:
        return best_name, APP_NAME_TO_PATH[best_name]

    return None


# ------- Small helper for testing -------
if __name__ == "__main__":
    print("Building index (may take a while)...")
    build_index(save=True)
    print("Done. Try example:")
    print("find_app('vs code') ->", find_app("vs code"))
    print("find_app('chrome') ->", find_app("chrome"))
