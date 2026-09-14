#!/usr/bin/env python3
"""
Garmin activity downloader (session-cookie / cURL based).

Reads two cURL commands from pipeline/curl.txt (exported from the browser
DevTools). Quel file contiene cookie di sessione ed e' escluso da git: vedi
pipeline/curl.txt.example per il formato e pipeline/README.md per come
rigenerarlo.

I due comandi attesi sono:
  1. LIST curl     -> activitylist-service/.../search/activities
  2. DOWNLOAD curl -> download-service/files/activity/<id>

It lists every activity (paginating the LIST curl), then downloads the .fit
file for each activity that is NOT already present locally. Activities already
downloaded are skipped, so re-running only fetches the new ones.

Usage:
  python pipeline/download_garmin.py andrea
  python pipeline/download_garmin.py andrea --dry-run
  python pipeline/download_garmin.py andrea --page-size 100 --delay 1.0

Update curl.txt with a fresh browser session when cookies expire.
"""

import argparse
import io
import json
import re
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent

sys.path.insert(0, str(SCRIPT_DIR))
import paths  # noqa: E402

# Magic bytes used to sanity-check a download really is an activity file and
# not an HTML/JSON error page returned by an expired session.
ZIP_MAGIC = b"PK\x03\x04"


def find_curl_file() -> Path:
    curl_file = SCRIPT_DIR / "curl.txt"
    if not curl_file.exists():
        raise FileNotFoundError(f"curl.txt not found at {curl_file}")
    return curl_file


def load_curls(curl_file: Path) -> Tuple[str, str]:
    """Split curl.txt into (list_curl, download_curl)."""
    content = curl_file.read_text()
    blocks = re.split(r"\n(?=curl\s)", content)
    blocks = [b.strip() for b in blocks if b.strip().startswith("curl")]
    if len(blocks) < 2:
        raise ValueError(
            f"Expected 2 curl commands in {curl_file} (list + download), "
            f"found {len(blocks)}"
        )
    return blocks[0], blocks[1]


def run_curl(curl_command: str, timeout: int = 60) -> bytes:
    """Execute a curl command and return the raw response bytes."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
        # -s silent, -S show errors, -f fail on HTTP >=400 (returns non-zero)
        f.write(curl_command)
        f.flush()
        temp_script = f.name
    try:
        result = subprocess.run(
            ["bash", temp_script], capture_output=True, timeout=timeout
        )
        if result.returncode != 0:
            err = result.stderr.decode("utf-8", errors="ignore").strip()
            raise RuntimeError(f"curl exited {result.returncode}: {err}")
        return result.stdout
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"curl timed out after {timeout}s")
    finally:
        Path(temp_script).unlink(missing_ok=True)


def set_list_page(list_curl: str, start: int, limit: int) -> str:
    """Rewrite the limit/start query params on the LIST curl URL."""
    curl = re.sub(r"([?&]limit=)\d+", rf"\g<1>{limit}", list_curl)
    curl = re.sub(r"([?&]start=)\d+", rf"\g<1>{start}", curl)
    return curl


def list_all_activities(list_curl: str, page_size: int) -> List[Dict]:
    """Page through the activity list until an empty page is returned."""
    print("📋 Listing activities...")
    activities: List[Dict] = []
    start = 0
    while True:
        page_curl = set_list_page(list_curl, start=start, limit=page_size)
        raw = run_curl(page_curl)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            preview = raw[:300].decode("utf-8", errors="ignore")
            raise RuntimeError(
                "List response was not JSON — session cookies likely expired.\n"
                f"Response preview: {preview}"
            )
        batch = data if isinstance(data, list) else data.get("activities", [])
        if not batch:
            break
        activities.extend(a for a in batch if isinstance(a, dict))
        print(f"  … fetched {len(activities)} so far")
        if len(batch) < page_size:
            break
        start += page_size
    print(f"✓ Found {len(activities)} activities")
    return activities


def existing_ids(activity_dir: Path) -> set:
    """ID gia' scaricati.

    Il separatore fra 'activity' e l'id e' tollerante: in archivio esistono file
    prodotti da versioni precedenti dello script con nomi tipo `activity22703772808.fit`
    o addirittura `activity?22608001977.fit`. Con un match troppo stretto quei file
    non venivano riconosciuti e l'attivita' veniva riscaricata a ogni esecuzione
    (e finiva due volte nei file trimestrali).
    """
    ids = set()
    for f in activity_dir.glob("activity*"):
        m = re.match(r"activity[^0-9]?(\d+)\.", f.name)
        if m:
            ids.add(int(m.group(1)))
    return ids


def extract_fit(raw: bytes) -> Optional[bytes]:
    """Return raw .fit bytes.

    Garmin's download-service returns a zip containing a single
    `<id>_ACTIVITY.fit`. If the payload is already a raw .FIT it is returned
    as-is. Returns None if the payload is neither a valid zip-with-fit nor a
    raw fit (e.g. an HTML/JSON error page from an expired session).
    """
    if raw[8:12] == b".FIT":
        return raw  # already a raw .fit
    if raw[:4] == ZIP_MAGIC:
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                fit_names = [n for n in zf.namelist() if n.lower().endswith(".fit")]
                if not fit_names:
                    return None
                return zf.read(fit_names[0])
        except zipfile.BadZipFile:
            return None
    return None


def download_activity(activity_id: int, download_curl: str) -> Optional[bytes]:
    """Download one activity and return the unzipped .fit bytes (or None)."""
    curl = re.sub(r"/activity/\d+", f"/activity/{activity_id}", download_curl)
    raw = run_curl(curl)
    return extract_fit(raw)


def repair_zips(activity_dir: Path) -> int:
    """Unzip any already-downloaded activity files still stored as zip in place."""
    repaired = failed = 0
    for f in sorted(activity_dir.glob("activity*.fit")):
        raw = f.read_bytes()
        if raw[:4] != ZIP_MAGIC:
            continue  # already a raw .fit
        fit = extract_fit(raw)
        if fit is None:
            print(f"  ❌ {f.name} — could not extract .fit")
            failed += 1
            continue
        f.write_bytes(fit)
        repaired += 1
        print(f"  ✓ {f.name}")
    print(f"\n✅ Unzipped {repaired} file(s)" + (f", {failed} failed" if failed else ""))
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("person", nargs="?", default="andrea",
                        help="Cartella atleta sotto athletes/ (default: andrea)")
    parser.add_argument("--page-size", type=int, default=100,
                        help="Activities per list page (default: 100)")
    parser.add_argument("--delay", type=float, default=1.0,
                        help="Seconds to wait between downloads (default: 1.0)")
    parser.add_argument("--dry-run", action="store_true",
                        help="List what would be downloaded without downloading")
    parser.add_argument("--repair", action="store_true",
                        help="Unzip already-downloaded files still stored as zip, then exit")
    args = parser.parse_args()

    person = args.person.strip().lower()
    paths.athlete_dir(person)  # esce con un messaggio utile se non esiste
    activity_dir = paths.raw_activities(person)
    activity_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print(f"🏃 Garmin downloader — person: {person}")
    print(f"📂 Output: {activity_dir}")
    print("=" * 60)

    if args.repair:
        print("🔧 Repair mode — unzipping existing files...")
        return repair_zips(activity_dir)

    curl_file = find_curl_file()
    list_curl, download_curl = load_curls(curl_file)

    try:
        activities = list_all_activities(list_curl, args.page_size)
    except RuntimeError as e:
        print(f"❌ {e}")
        return 1

    if not activities:
        print("⚠️  No activities returned.")
        return 0

    have = existing_ids(activity_dir)
    to_download = [a for a in activities if int(a["activityId"]) not in have]

    print(f"\n📊 {len(activities)} total · {len(have)} already downloaded · "
          f"{len(to_download)} to download")

    if not to_download:
        print("✅ Everything is already downloaded — nothing to do.")
        return 0

    if args.dry_run:
        print("\n🔍 Dry run — would download:")
        for a in to_download:
            print(f"   {a['activityId']}  {a.get('startTimeLocal', '?')}  "
                  f"{a.get('activityName', '')}")
        return 0

    downloaded, failed = 0, []
    print(f"\n📥 Downloading {len(to_download)} activities...")
    for i, a in enumerate(to_download, 1):
        aid = int(a["activityId"])
        name = a.get("activityName", "")
        try:
            data = download_activity(aid, download_curl)
        except RuntimeError as e:
            print(f"  ❌ [{i}/{len(to_download)}] {aid} — {e}")
            failed.append(aid)
            if "429" in str(e):
                print("  ⛔ Rate limited (429). Stopping. Re-run later.")
                break
            continue

        if data is None:
            print(f"  ❌ [{i}/{len(to_download)}] {aid} — invalid response "
                  f"(session expired?). Stopping.")
            failed.append(aid)
            break

        (activity_dir / f"activity_{aid}.fit").write_bytes(data)
        downloaded += 1
        print(f"  ✓ [{i}/{len(to_download)}] {aid}  {name}")
        if args.delay:
            time.sleep(args.delay)

    print(f"\n✅ Downloaded {downloaded}/{len(to_download)} new activities")
    if failed:
        print(f"⚠️  {len(failed)} failed: {failed}")
        print("   If the session expired, refresh curl.txt and re-run "
              "(already-downloaded activities are skipped).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
