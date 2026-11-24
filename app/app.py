"""FedEx Express air network explorer (BTS T-100). Run: uv run streamlit run app/app.py"""
from __future__ import annotations

import sys
from pathlib import Path

import altair as alt
import duckdb
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from analysis.forecast import forecast  # noqa: E402
from analysis.whatif import hub_disruption  # noqa: E402

FULL, DEMO = ROOT / "data" / "warehouse.duckdb", ROOT / "demo" / "network.duckdb"
DB = FULL if FULL.exists() else DEMO
ORANGE, PURPLE, GREY = "#FF6200", "#4D148C", "#9AA0A6"

st.set_page_config(page_title="FedEx Air Network", page_icon="✈️", layout="wide")


@st.cache_resource
def con():
    return duckdb.connect(str(DB), read_only=True)


@st.cache_data
def q(sql: str, params: tuple = ()) -> pd.DataFrame:
    return con().execute(sql, list(params)).df()


months = q("select min(month_start) lo, max(month_start) hi from fct_fedex_route_month").iloc[0]
st.title("FedEx Express air network, from public flight data")
st.caption(f"U.S. DOT / BTS T-100 segment data, every FedEx Express (carrier FX) flight segment reported, "
           f"{months.lo:%b %Y} to {months.hi:%b %Y}. Weights are freight + mail in pounds.")

network = q("""select month_start, sum(freight_lbs + mail_lbs) cargo, sum(payload_lbs) payload,
               sum(departures_performed) departures from fct_fedex_route_month group by 1 order by 1""")
network["load_factor"] = network.cargo / network.payload
last12, prev12 = network.tail(12), network.iloc[-24:-12]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Cargo, last 12 months", f"{last12.cargo.sum() / 1e9:.2f}B lbs",
          f"{last12.cargo.sum() / prev12.cargo.sum() - 1:+.1%} vs prior 12")
c2.metric("Departures, last 12 months", f"{last12.departures.sum():,.0f}",
          f"{last12.departures.sum() / prev12.departures.sum() - 1:+.1%}")
c3.metric("Load factor, last 12 months", f"{last12.cargo.sum() / last12.payload.sum():.1%}",
          help="Cargo carried / payload capacity flown, by weight")
mem = q("""select sum(handled_lbs) filter (where airport = 'MEM') / sum(handled_lbs) * 2 share
           from fct_fedex_airport_month where month_start >= ?""", (last12.month_start.min(),)).iloc[0, 0]
c4.metric("Cargo touching Memphis", f"{mem:.0%}", help="Share of all cargo that departs or arrives at MEM")

tab_net, tab_hubs, tab_fleet, tab_peers, tab_fc, tab_whatif = st.tabs(
    ["Network", "Hubs", "Fleet", "Peers", "Forecast", "Hub disruption what-if"])

with tab_net:
    st.subheader("Monthly cargo and how full the aircraft flew")
    base = alt.Chart(network).encode(x=alt.X("month_start:T", title=None))
    st.altair_chart(base.mark_area(color=ORANGE, opacity=0.85).encode(
        y=alt.Y("cargo:Q", title="Cargo (lbs)", axis=alt.Axis(format="~s")),
        tooltip=[alt.Tooltip("month_start:T", format="%b %Y"), alt.Tooltip("cargo:Q", format=",.0f")]),
        width="stretch")
    st.altair_chart(base.mark_line(color=PURPLE, point=True).encode(
        y=alt.Y("load_factor:Q", title="Load factor", axis=alt.Axis(format="%"), scale=alt.Scale(zero=False)),
        tooltip=[alt.Tooltip("month_start:T", format="%b %Y"), alt.Tooltip("load_factor:Q", format=".1%")]),
        width="stretch")
    season = q("""select year(month_start) yr, month(month_start) m, sum(freight_lbs + mail_lbs) cargo
                  from fct_fedex_route_month group by all""")
    season["vs_year_avg"] = season.cargo / season.groupby("yr").cargo.transform("mean") - 1
    st.subheader("Seasonality: each month vs that year's average")
    st.altair_chart(alt.Chart(season).mark_rect().encode(
        x=alt.X("m:O", title="Month"), y=alt.Y("yr:O", title=None),
        color=alt.Color("vs_year_avg:Q", scale=alt.Scale(scheme="purpleorange", domainMid=0), title="vs avg",
                        legend=alt.Legend(format="+%")),
        tooltip=["yr", "m", alt.Tooltip("vs_year_avg:Q", format="+.1%")]), width="stretch")

with tab_hubs:
    year = st.selectbox("Year", sorted(q("select distinct year(month_start) y from fct_fedex_airport_month").y,
                                       reverse=True))
    hubs = q("""select airport, any_value(city) city, sum(handled_lbs) handled, sum(departures) departures
                from fct_fedex_airport_month where year(month_start) = ? group by 1 order by 3 desc limit 15""",
             (int(year),))
    st.altair_chart(alt.Chart(hubs).mark_bar(color=ORANGE).encode(
        x=alt.X("handled:Q", title="Cargo handled, in + out (lbs)", axis=alt.Axis(format="~s")),
        y=alt.Y("airport:N", sort="-x", title=None),
        tooltip=["airport", "city", alt.Tooltip("handled:Q", format=",.0f"), alt.Tooltip("departures:Q", format=",")]),
        width="stretch")
    routes = q("""select origin || ' → ' || dest route, sum(freight_lbs + mail_lbs) cargo,
                  sum(departures_performed) departures, sum(freight_lbs + mail_lbs) / sum(payload_lbs) load_factor
                  from fct_fedex_route_month where year = ? group by 1 order by 2 desc limit 20""", (int(year),))
    st.subheader(f"Top 20 routes by cargo, {year}")
    st.dataframe(routes.style.format({"cargo": "{:,.0f}", "departures": "{:,.0f}", "load_factor": "{:.1%}"}),
                 width="stretch", hide_index=True)

with tab_fleet:
    fleet = q("""select aircraft_name, sum(departures) departures, sum(block_hours) block_hours,
                 sum(cargo_lbs) cargo, sum(cargo_lbs) / sum(payload_lbs) load_factor,
                 sum(payload_lbs) / sum(departures) payload_per_departure
                 from fct_fedex_aircraft_month where month_start >= ? group by 1 having sum(departures) > 500
                 order by cargo desc""", (last12.month_start.min(),))
    st.subheader("Fleet, last 12 months")
    st.altair_chart(alt.Chart(fleet).mark_circle(color=PURPLE, opacity=0.8).encode(
        x=alt.X("payload_per_departure:Q", title="Average payload capacity per departure (lbs)",
                axis=alt.Axis(format="~s")),
        y=alt.Y("load_factor:Q", title="Load factor", axis=alt.Axis(format="%")),
        size=alt.Size("cargo:Q", title="Cargo"),
        tooltip=["aircraft_name", alt.Tooltip("departures:Q", format=","), alt.Tooltip("load_factor:Q", format=".1%"),
                 alt.Tooltip("cargo:Q", format=",.0f")]), width="stretch")
    st.dataframe(fleet.style.format({"departures": "{:,.0f}", "block_hours": "{:,.0f}", "cargo": "{:,.0f}",
                                     "load_factor": "{:.1%}", "payload_per_departure": "{:,.0f}"}),
                 width="stretch", hide_index=True)

with tab_peers:
    peers = q("""select month_start, carrier_name, freight_lbs + mail_lbs cargo, load_factor
                 from fct_cargo_carrier_month where carrier in ('FX', '5X', '5Y', '8C', 'KAQ') order by 1""")
    st.subheader("FedEx vs other U.S. cargo carriers")
    st.altair_chart(alt.Chart(peers).mark_line().encode(
        x=alt.X("month_start:T", title=None), y=alt.Y("cargo:Q", title="Cargo (lbs)", axis=alt.Axis(format="~s")),
        color=alt.Color("carrier_name:N", title=None)), width="stretch")
    st.caption("UPS, Atlas Air, Air Transport International and Kalitta Air report under their own carrier codes.")
    st.subheader("U.S. domestic air cargo: FedEx vs UPS")
    dom = q("""select month_start, case carrier when 'FX' then 'FedEx' else 'UPS' end carrier, domestic_cargo_lbs cargo
               from fct_cargo_carrier_month where carrier in ('FX', '5X') order by 1""")
    wide = dom.pivot(index="month_start", columns="carrier", values="cargo")
    ahead = wide[wide.UPS > wide.FedEx]
    if len(ahead):
        st.write(f"UPS carried more U.S. domestic air cargo than FedEx in **{len(ahead)} of {len(wide)} months**, "
                 f"the first in **{ahead.index.min():%B %Y}** and every month since. The timing matches the "
                 "publicly reported end of FedEx's U.S. Postal Service air contract in September 2024; T-100 "
                 "does not identify shippers, so the data shows the shift, not its cause.")
    rule = alt.Chart(pd.DataFrame({"m": [ahead.index.min()]})).mark_rule(strokeDash=[4, 3], color=GREY).encode(
        x="m:T") if len(ahead) else alt.Chart(pd.DataFrame())
    st.altair_chart(alt.Chart(dom).mark_line().encode(
        x=alt.X("month_start:T", title=None),
        y=alt.Y("cargo:Q", title="Domestic cargo (lbs)", axis=alt.Axis(format="~s")),
        color=alt.Color("carrier:N", scale=alt.Scale(domain=["FedEx", "UPS"], range=[PURPLE, "#8B5E34"]), title=None),
        tooltip=[alt.Tooltip("month_start:T", format="%b %Y"), "carrier", alt.Tooltip("cargo:Q", format=",.0f")])
        + rule, width="stretch")

with tab_fc:
    series = network.set_index("month_start").cargo
    best, scores, future = forecast(series)
    st.subheader("Next 12 months of cargo")
    st.write(f"Each method was scored on the last 12 months it never saw. Best: **{best.replace('_', ' ')}**, "
             f"off by **{scores.iloc[0].mape:.1%}** a month on average (MAPE).")
    hist = network[["month_start", "cargo"]].rename(columns={"cargo": "lbs"}).assign(kind="actual")
    fut = future.rename(columns={"forecast": "lbs"}).assign(kind="forecast")
    st.altair_chart(alt.Chart(pd.concat([hist.tail(36), fut])).mark_line(point=True).encode(
        x=alt.X("month_start:T", title=None), y=alt.Y("lbs:Q", title="Cargo (lbs)", axis=alt.Axis(format="~s")),
        color=alt.Color("kind:N", scale=alt.Scale(range=[ORANGE, PURPLE]), title=None),
        strokeDash=alt.StrokeDash("kind:N", legend=None)), width="stretch")
    st.dataframe(scores.style.format({"mape": "{:.1%}"}), hide_index=True)

with tab_whatif:
    st.subheader("If a hub loses capacity for a month, can the rest of the network absorb it?")
    st.write("Displaced cargo is compared with lift that already flew empty out of the backup hubs that month. "
             "No extra flights, aircraft or crews are assumed. A first-pass screen, not a routing model.")
    a, b, c = st.columns(3)
    month = a.selectbox("Month", list(network.month_start.dt.strftime("%Y-%m-01"))[::-1])
    hub = b.selectbox("Hub", ["MEM", "IND", "ANC", "OAK", "EWR"])
    lost = c.slider("Capacity lost (%)", 5, 100, 25, 5) / 100
    backups = st.multiselect("Backup hubs", ["MEM", "IND", "ANC", "OAK", "EWR", "AFW", "GSO", "MIA"],
                             default=[h for h in ["IND", "OAK", "EWR"] if h != hub])
    r = hub_disruption(con(), month, hub, lost, [x for x in backups if x != hub])
    m1, m2, m3 = st.columns(3)
    m1.metric("Cargo displaced", f"{r['displaced_lbs'] / 1e6:,.1f}M lbs")
    m2.metric("Spare lift at backups", f"{r['spare_total_lbs'] / 1e6:,.1f}M lbs")
    m3.metric("Covered", f"{r['covered_share']:.0%}", f"{r['uncovered_lbs'] / 1e6:,.1f}M lbs uncovered",
              delta_color="off")

st.divider()
st.caption("Data: U.S. Department of Transportation, Bureau of Transportation Statistics, T-100 Segment (All "
           "Carriers). Public, monthly, self-reported by carriers; no package counts, ground network or costs. "
           "Independent analysis, not affiliated with FedEx. Code: github.com/Nezz23/fedex-air-network")
