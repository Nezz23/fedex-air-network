"""Download BTS T-100 Segment (All Carriers) yearly files from TranStats.

    python3 scripts/download_t100.py 2019 2026

TranStats is an ASP.NET form: GET the page for its view state, then POST the year, every month and the columns
we use. The server answers with a zip of one CSV. Files land in data/raw/t100_segment_<year>.zip.
"""
import http.cookiejar
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

URL = "https://www.transtats.bts.gov/DL_SelectFields.aspx?gnoyr_VQ=FMG&QO_fu146_anzr=Nv4%20Pn44vr45"
COLUMNS = [
    "DEPARTURES_SCHEDULED", "DEPARTURES_PERFORMED", "PAYLOAD", "SEATS", "PASSENGERS", "FREIGHT", "MAIL",
    "DISTANCE", "RAMP_TO_RAMP", "AIR_TIME", "UNIQUE_CARRIER", "UNIQUE_CARRIER_NAME", "CARRIER_GROUP_NEW",
    "ORIGIN", "ORIGIN_CITY_NAME", "ORIGIN_STATE_ABR", "ORIGIN_COUNTRY", "DEST", "DEST_CITY_NAME",
    "DEST_STATE_ABR", "DEST_COUNTRY", "AIRCRAFT_GROUP", "AIRCRAFT_TYPE", "AIRCRAFT_CONFIG", "YEAR", "MONTH",
    "CLASS", "DATA_SOURCE",
]
OUT = Path(__file__).resolve().parent.parent / "data" / "raw"


def hidden(html, name):
    key = re.escape(name)
    m = re.search(rf'name="{key}"[^>]*value="([^"]*)"', html) or re.search(rf'value="([^"]*)"[^>]*name="{key}"', html)
    return m.group(1) if m else ""


def download(year, opener):
    html = opener.open(URL, timeout=60).read().decode("utf-8", "ignore")
    form = {
        "__EVENTTARGET": "", "__EVENTARGUMENT": "", "__LASTFOCUS": "",
        "__VIEWSTATE": hidden(html, "__VIEWSTATE"),
        "__VIEWSTATEGENERATOR": hidden(html, "__VIEWSTATEGENERATOR"),
        "__EVENTVALIDATION": hidden(html, "__EVENTVALIDATION"),
        "txtSearch": "", "cboGeography": "All", "cboYear": str(year), "cboPeriod": "All",
        "btnDownload": "Download",
    }
    form.update({c: "on" for c in COLUMNS})
    data = urllib.parse.urlencode(form).encode()
    with opener.open(urllib.request.Request(URL, data=data), timeout=240) as resp:
        body = resp.read()
        kind = resp.headers.get("Content-Type", "")
    if not body.startswith(b"PK"):
        raise RuntimeError(f"{year}: expected a zip, got {kind} ({len(body)} bytes)")
    path = OUT / f"t100_segment_{year}.zip"
    path.write_bytes(body)
    print(f"{year}: {path.name} {len(body) / 1e6:.1f} MB", flush=True)


def main():
    first, last = int(sys.argv[1]), int(sys.argv[2])
    OUT.mkdir(parents=True, exist_ok=True)
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    opener.addheaders = [("User-Agent", "Mozilla/5.0 (research download)")]
    for year in range(first, last + 1):
        if (OUT / f"t100_segment_{year}.zip").exists():
            print(f"{year}: already downloaded")
            continue
        for attempt in range(1, 4):  # TranStats sometimes stalls; a fresh request usually goes through
            try:
                download(year, opener)
                break
            except OSError as e:
                print(f"{year}: attempt {attempt} failed ({e}); retrying", flush=True)
                time.sleep(10 * attempt)
        else:
            raise SystemExit(f"{year}: gave up after 3 attempts")


if __name__ == "__main__":
    main()
