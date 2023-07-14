"""Example demonstrating real-time comparison of stock prices."""

import functools

import pandas as pd
from pyrate_limiter import Duration, Limiter, RequestRate
import pyrona as pr
from requests import Session
import requests_cache
from requests_cache import CacheMixin, SQLiteCache
from requests_ratelimiter import LimiterMixin, MemoryQueueBucket
import yfinance as yf


class CachedLimiterSession(CacheMixin, LimiterMixin, Session):
    """Session class."""
    pass


def _msft(session: CachedLimiterSession) -> pd.DataFrame:
    ticker = yf.Ticker("msft", session=session)
    return ticker.history(period="1mo")


def _aapl(session: CachedLimiterSession) -> pd.DataFrame:
    ticker = yf.Ticker("aapl", session=session)
    return ticker.history(period="1mo")


def _amzn(session: CachedLimiterSession) -> pd.DataFrame:
    ticker = yf.Ticker("amzn", session=session)
    return ticker.history(period="1mo")


def _spy(session: CachedLimiterSession) -> pd.DataFrame:
    ticker = yf.Ticker("spy", session=session)
    return ticker.history(period="1mo")


def _aggregate_price(*constituents: pd.DataFrame):
    return functools.reduce(lambda x, y: x + y,
                            [c["Open"] for c in constituents])


def _adjust(lh, rh):
    ratio = rh.iloc[0] / lh.iloc[0]
    return pd.DataFrame({f"lh {lh.name}": lh * ratio, f"rh {rh.name}": rh})


def _main():
    session = CachedLimiterSession(
        # max 2 requests per 5 seconds
        limiter=Limiter(RequestRate(2, Duration.SECOND*5)),
        bucket_class=MemoryQueueBucket,
        backend=SQLiteCache("yfinance.cache"),
    )

    session = requests_cache.CachedSession("yfinance.cache")
    session.headers["User-agent"] = "my-program/1.0"

    msft_r = pr.Region("msft").make_shareable()
    aapl_r = pr.Region("aapl").make_shareable()
    amzn_r = pr.Region("amzn").make_shareable()

    # when msft_r as m:
    @pr.when(msft_r)
    def _(m):
        m.price = _msft(session)

    # when aapl_r as m:
    @pr.when(aapl_r)
    def _(m):
        m.price = _aapl(session)

    # when amzn_r as m:
    @pr.when(amzn_r)
    def _(m):
        m.price = _amzn(session)

    big_tech_r = pr.Region("big_tech").make_shareable()

    # when big_tech_r, msft_r, aapl_r, amzn_r as b, m, a, z:
    @pr.when(big_tech_r, msft_r, aapl_r, amzn_r)
    def _(b, m, a, z):
        b.price = _aggregate_price(m.price, a.price, z.price)

    spy_r = pr.Region("spy").make_shareable()

    # when spy_r as s:
    @pr.when(spy_r)
    def _(s):
        s.price = _spy(session)["Open"]

    # when big_tech_r, spy_r as b, s:
    @pr.when(big_tech_r, spy_r)
    def _(b, s):
        adj = _adjust(b.price, s.price)
        print(adj)


if __name__ == "__main__":
    _main()
    pr.wait()
