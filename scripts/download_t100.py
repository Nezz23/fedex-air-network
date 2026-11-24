"""Download BTS T-100 Segment (All Carriers) yearly files from TranStats.

    python3 scripts/download_t100.py 2019 2026 [--monthly]

TranStats is an ASP.NET form: GET the page for its view state, then POST the year, every month and the columns
we use. The server answers with a zip of one CSV. Files land in data/raw/t100_segment_<year>.zip.
"""
import http.cookiejar
import io
import re
import sys
import time
import urllib.parse
import urllib.request
import zipfile
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


def fetch(year, period, opener):
    """One POST; returns the zip bytes for a year (period "All") or a single month."""
    html = opener.open(URL, timeout=60).read().decode("utf-8", "ignore")
    form = {
        "__EVENTTARGET": "", "__EVENTARGUMENT": "", "__LASTFOCUS": "",
        "__VIEWSTATE": hidden(html, "__VIEWSTATE"),
        "__VIEWSTATEGENERATOR": hidden(html, "__VIEWSTATEGENERATOR"),
        "__EVENTVALIDATION": hidden(html, "__EVENTVALIDATION"),
        "txtSearch": "", "cboGeography": "All", "cboYear": str(year), "cboPeriod": str(period),
        "btnDownload": "Download",
    }
    form.update({c: "on" for c in COLUMNS})
    data = urllib.parse.urlencode(form).encode()
    with opener.open(urllib.request.Request(URL, data=data), timeout=180) as resp:
        body = resp.read()
        kind = resp.headers.get("Content-Type", "")
    if not body.startswith(b"PK"):
        raise RuntimeError(f"{year}/{period}: expected a zip, got {kind} ({len(body)} bytes)")
    return body


def download(year, opener, monthly=False):
    path = OUT / f"t100_segment_{year}.zip"
    try:
        if monthly:
            raise TimeoutError("--monthly")
        body = fetch(year, "All", opener)
        path.write_bytes(body)
    except OSError as e:
        # A whole year can take TranStats longer to build than it will wait; months are small. Ask month by month
        # and stitch the CSVs into the same one-file-per-year zip the loader expects.
        print(f"{year}: whole-year request failed ({e}); fetching month by month", flush=True)
        header, rows = None, []
        for month in range(1, 13):
            try:
                body = fetch(year, month, opener)
            except RuntimeError:
                if not rows:
                    raise
                print(f"  {year}-{month:02d}: not published yet; keeping {month - 1} months", flush=True)
                break  # BTS publishes with a lag: the current year stops at the latest released month
            with zipfile.ZipFile(io.BytesIO(body)) as z:
                [member] = [m for m in z.namelist() if m.lower().endswith(".csv")]
                lines = z.read(member).decode("utf-8").splitlines(keepends=True)
            header = header or lines[0]
            if lines[0] != header:
                raise RuntimeError(f"{year}/{month}: columns differ from earlier months") from None
            rows.extend(lines[1:])
            print(f"  {year}-{month:02d}: {len(lines) - 1:,} rows", flush=True)
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("T_T100_SEGMENT_ALL_CARRIER.csv", header + "".join(rows))
    print(f"{year}: {path.name} {path.stat().st_size / 1e6:.1f} MB", flush=True)


def main():
    monthly = "--monthly" in sys.argv
    first, last = (int(a) for a in sys.argv[1:] if a != "--monthly")
    OUT.mkdir(parents=True, exist_ok=True)
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    opener.addheaders = [("User-Agent", "Mozilla/5.0 (research download)")]
    for year in range(first, last + 1):
        if (OUT / f"t100_segment_{year}.zip").exists():
            print(f"{year}: already downloaded")
            continue
        for attempt in range(1, 4):  # TranStats sometimes stalls; a fresh request usually goes through
            try:
                download(year, opener, monthly)
                break
            except (OSError, RuntimeError) as e:
                print(f"{year}: attempt {attempt} failed ({e}); retrying", flush=True)
                time.sleep(10 * attempt)
        else:
            raise SystemExit(f"{year}: gave up after 3 attempts")


if __name__ == "__main__":
    main()
