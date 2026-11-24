"""Copy the four marts the app reads into demo/network.duckdb, small enough to commit for the hosted app.

    uv run python deploy/export_demo.py
"""
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
TABLES = ["fct_fedex_route_month", "fct_fedex_airport_month", "fct_fedex_aircraft_month", "fct_cargo_carrier_month"]


def main() -> None:
    out = ROOT / "demo" / "network.duckdb"
    out.unlink(missing_ok=True)
    con = duckdb.connect(str(out))
    con.execute(f"attach '{ROOT / 'data' / 'warehouse.duckdb'}' as src (read_only)")
    for t in TABLES:
        con.execute(f"create table {t} as select * from src.main.{t}")
        print(t, con.execute(f"select count(*) from {t}").fetchone()[0])
    con.execute("detach src")
    con.close()
    print(f"{out.name}: {out.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
