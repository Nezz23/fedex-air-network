"""Load the downloaded T-100 yearly zips into DuckDB, untouched: raw.t100_segment.

    uv run python -m ingestion.load_raw

Every carrier is kept (peers like UPS and Atlas are the benchmark). Each file is loaded as text, so typing and
rules live in dbt where they are tested. Re-running replaces a year rather than duplicating it.
"""
from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
DB = ROOT / "data" / "warehouse.duckdb"


def load(db_path: Path = DB, raw_dir: Path = RAW) -> dict[int, int]:
    con = duckdb.connect(str(db_path))
    con.execute("create schema if not exists raw")
    loaded: dict[int, int] = {}
    for path in sorted(raw_dir.glob("t100_segment_*.zip")):
        year = int(path.stem.rsplit("_", 1)[1])
        with zipfile.ZipFile(path) as z, tempfile.TemporaryDirectory() as tmp:
            [member] = [m for m in z.namelist() if m.lower().endswith(".csv")]
            csv = Path(z.extract(member, tmp))
            con.execute(
                f"""create or replace temp table batch as
                select *, '{path.name}' as source_file, now() as loaded_at
                from read_csv(?, header = true, all_varchar = true)""",
                [str(csv)],
            )
        bad = con.execute("select count(*) from batch where year <> ?", [str(year)]).fetchone()[0]
        if bad:
            raise ValueError(f"{path.name}: {bad} rows are not from {year}")
        con.execute("create table if not exists raw.t100_segment as select * from batch limit 0")
        con.execute("delete from raw.t100_segment where year = ?", [str(year)])
        con.execute("insert into raw.t100_segment by name select * from batch")
        loaded[year] = con.execute("select count(*) from batch").fetchone()[0]
        print(f"{year}: {loaded[year]:,} rows from {path.name}")
    con.close()
    return loaded


if __name__ == "__main__":
    load()
