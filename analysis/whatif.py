"""Hub disruption what-if: if a hub loses part of its outbound capacity for a month, can the rest of the
network absorb the displaced cargo?

Displaced cargo  = hub's outbound cargo x capacity lost.
Spare capacity   = payload - cargo on every route out of the backup hubs that month (lift that already flew
                   empty). Only lift that exists is counted: no extra flights, aircraft or crews.
This is a first-pass screen a planner would refine, not a routing model.
"""
from __future__ import annotations

import duckdb


def hub_disruption(con: duckdb.DuckDBPyConnection, month: str, hub: str, capacity_lost: float,
                   backups: list[str]) -> dict:
    if not 0 <= capacity_lost <= 1:
        raise ValueError("capacity_lost must be between 0 and 1")
    out = con.execute("""
        select sum(freight_lbs + mail_lbs)::double as cargo, sum(payload_lbs)::double as payload
        from fct_fedex_route_month where month_start = ?::date and origin = ?""", [month, hub]).fetchone()
    if out[0] is None:
        raise ValueError(f"no FedEx departures from {hub} in {month}")
    spare = con.execute("""
        select origin, sum(payload_lbs - freight_lbs - mail_lbs)::double as spare_lbs
        from fct_fedex_route_month where month_start = ?::date and origin in (select unnest(?))
        group by 1 order by 1""", [month, backups]).fetchall()
    displaced = out[0] * capacity_lost
    total_spare = sum(s for _, s in spare)
    return {
        "month": month, "hub": hub, "capacity_lost": capacity_lost,
        "hub_outbound_cargo_lbs": out[0], "displaced_lbs": displaced,
        "spare_by_backup_lbs": dict(spare), "spare_total_lbs": total_spare,
        "covered_share": min(1.0, total_spare / displaced) if displaced else 1.0,
        "uncovered_lbs": max(0.0, displaced - total_spare),
    }
