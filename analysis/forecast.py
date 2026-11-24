"""Monthly FedEx freight forecast with an honest backtest.

Three simple, explainable methods, each scored on the most recent 12 months it never saw:
  seasonal_naive     next month = same month last year
  seasonal_trend     same month last year x (last 12 months / the 12 before), i.e. last year's shape at today's level
  moving_average     mean of the last 3 months (no seasonality)
The method with the lowest backtest error (MAPE) is used for the forward forecast.
"""
from __future__ import annotations

import pandas as pd

HORIZON = 12


def seasonal_naive(history: pd.Series, steps: int) -> list[float]:
    return [float(history.iloc[-12 + (i % 12)]) for i in range(steps)]


def seasonal_trend(history: pd.Series, steps: int) -> list[float]:
    level = history.iloc[-12:].sum() / history.iloc[-24:-12].sum()
    return [float(history.iloc[-12 + (i % 12)] * level) for i in range(steps)]


def moving_average(history: pd.Series, steps: int) -> list[float]:
    return [float(history.iloc[-3:].mean())] * steps


METHODS = {"seasonal_naive": seasonal_naive, "seasonal_trend": seasonal_trend, "moving_average": moving_average}


def mape(actual: pd.Series, predicted: list[float]) -> float:
    return float(((actual - pd.Series(predicted, index=actual.index)).abs() / actual).mean())


def backtest(series: pd.Series, horizon: int = HORIZON) -> pd.DataFrame:
    """Fit on everything except the last `horizon` months, score on those months."""
    train, test = series.iloc[:-horizon], series.iloc[-horizon:]
    rows = []
    for name, fn in METHODS.items():
        rows.append({"method": name, "mape": mape(test, fn(train, horizon))})
    return pd.DataFrame(rows).sort_values("mape").reset_index(drop=True)


def forecast(series: pd.Series, horizon: int = HORIZON) -> tuple[str, pd.DataFrame, pd.DataFrame]:
    scores = backtest(series, horizon)
    best = scores.iloc[0]["method"]
    future_index = pd.date_range(series.index[-1] + pd.offsets.MonthBegin(1), periods=horizon, freq="MS")
    future = pd.DataFrame({"month_start": future_index, "forecast": METHODS[best](series, horizon)})
    return best, scores, future
