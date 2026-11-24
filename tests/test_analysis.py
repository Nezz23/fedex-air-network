import duckdb
import pandas as pd
import pytest

from analysis.forecast import backtest, forecast, mape, seasonal_naive, seasonal_trend
from analysis.whatif import hub_disruption


def monthly(values, start="2022-01-01"):
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq="MS"), dtype=float)


def test_seasonal_methods_repeat_last_years_shape_at_the_right_level():
    year = [10, 8, 12, 11, 10, 9, 13, 12, 11, 14, 10, 12]
    history = monthly(year + [v * 2 for v in year])  # the second year doubled
    assert seasonal_naive(history, 3) == [20, 16, 24]
    assert seasonal_trend(history, 3) == [40, 32, 48]  # level doubled again


def test_backtest_picks_the_method_that_fits_a_trending_seasonal_series():
    year = [10, 8, 12, 11, 10, 9, 13, 12, 11, 14, 10, 12]
    series = monthly([v * 1.1 ** k for k in range(4) for v in year])  # +10% a year, same shape
    scores = backtest(series)
    assert scores.iloc[0]["method"] == "seasonal_trend"
    assert scores.iloc[0]["mape"] == pytest.approx(0, abs=1e-9)
    best, _, future = forecast(series)
    assert best == "seasonal_trend" and len(future) == 12
    assert future["month_start"].iloc[0] == pd.Timestamp("2026-01-01")


def test_mape():
    assert mape(monthly([100, 200]), [110, 180]) == pytest.approx(0.1)


@pytest.fixture
def con():
    c = duckdb.connect()
    c.execute("""create table fct_fedex_route_month as select * from (values
        (date '2025-10-01', 'MEM', 'LAX', 800.0, 0.0, 1000.0),
        (date '2025-10-01', 'MEM', 'EWR', 200.0, 0.0, 400.0),
        (date '2025-10-01', 'IND', 'LAX', 300.0, 0.0, 500.0),
        (date '2025-10-01', 'OAK', 'IND', 50.0, 0.0, 150.0)
    ) t(month_start, origin, dest, freight_lbs, mail_lbs, payload_lbs)""")
    return c


def test_disruption_compares_displaced_cargo_with_spare_lift(con):
    r = hub_disruption(con, "2025-10-01", "MEM", 0.25, ["IND", "OAK"])
    assert r["hub_outbound_cargo_lbs"] == 1000
    assert r["displaced_lbs"] == 250
    assert r["spare_by_backup_lbs"] == {"IND": 200, "OAK": 100}
    assert r["covered_share"] == 1.0 and r["uncovered_lbs"] == 0

    worse = hub_disruption(con, "2025-10-01", "MEM", 0.5, ["IND"])
    assert worse["covered_share"] == pytest.approx(0.4) and worse["uncovered_lbs"] == 300


def test_disruption_rejects_bad_inputs(con):
    with pytest.raises(ValueError, match="between 0 and 1"):
        hub_disruption(con, "2025-10-01", "MEM", 1.5, ["IND"])
    with pytest.raises(ValueError, match="no FedEx departures"):
        hub_disruption(con, "2025-10-01", "XXX", 0.1, ["IND"])


def test_level_x_season_recovers_from_a_structural_break():
    from analysis.forecast import level_x_season
    shape = [0.9, 0.8, 1.0, 1.0, 1.0, 1.0, 1.1, 1.0, 1.0, 1.1, 1.0, 1.1]
    before = [100 * s for s in shape] * 2
    after = [70 * s for s in shape]  # a lost contract: same seasonality, 30% lower level
    history = monthly(before + after)
    got = level_x_season(history, 12)
    assert got == pytest.approx([70 * s for s in shape], rel=0.02)
    assert seasonal_naive(history, 1)[0] == pytest.approx(63)  # copies last year: right here, but wrong after a break
