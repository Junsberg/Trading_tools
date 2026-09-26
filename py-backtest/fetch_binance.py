"""바이낸스 USDT-M 선물 캔들 다운로드 (공개 API, 키 불필요)

트레이딩뷰 API 는 한 번에 ~5000봉(5분봉 17일)만 주지만, 바이낸스는 몇 년치를 무료로 준다.
파이썬 엔진의 기본 데이터 소스.

사용:
    python fetch_binance.py                                   # BTCUSDT 5m, 최근 180일
    python fetch_binance.py --symbol ETHUSDT --interval 15m --days 365
    python fetch_binance.py --start 2026-01-01 --end 2026-09-25

저장: data/<SYMBOL>_<interval>.csv  (time = UTC 초, 기존 파일이 있으면 이어서 받음)
"""
import argparse
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

sys.stdout.reconfigure(encoding="utf-8")

BASE = "https://fapi.binance.com/fapi/v1/klines"
LIMIT = 1500
COLS = ["time", "open", "high", "low", "close", "volume", "close_time", "quote_volume",
        "trades", "taker_buy_base", "taker_buy_quote", "ignore"]


def fetch(symbol: str, interval: str, start_ms: int, end_ms: int) -> pd.DataFrame:
    rows = []
    cur = start_ms
    while cur < end_ms:
        r = requests.get(BASE, params={"symbol": symbol, "interval": interval, "startTime": cur,
                                       "endTime": end_ms, "limit": LIMIT}, timeout=30)
        if r.status_code == 429:
            time.sleep(5)
            continue
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        rows.extend(batch)
        cur = batch[-1][0] + 1
        print(f"\r  {datetime.fromtimestamp(cur / 1000, tz=timezone.utc):%Y-%m-%d %H:%M}  {len(rows):,}봉", end="")
        time.sleep(0.15)  # 레이트리밋 여유
    print()
    df = pd.DataFrame(rows, columns=COLS)
    df = df[["time", "open", "high", "low", "close", "volume", "trades", "taker_buy_base", "quote_volume"]].astype(float)
    df["time"] = (df["time"] // 1000).astype(int)
    df["trades"] = df["trades"].astype(int)
    return df


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="BTCUSDT")
    ap.add_argument("--interval", default="5m")
    ap.add_argument("--days", type=int, default=180)
    ap.add_argument("--start", default=None, help="YYYY-MM-DD (UTC)")
    ap.add_argument("--end", default=None, help="YYYY-MM-DD (UTC, 기본 지금)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    end = datetime.strptime(a.end, "%Y-%m-%d").replace(tzinfo=timezone.utc) if a.end else datetime.now(timezone.utc)
    start = datetime.strptime(a.start, "%Y-%m-%d").replace(tzinfo=timezone.utc) if a.start else end - timedelta(days=a.days)

    out = a.out or os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", f"{a.symbol}_{a.interval}.csv")
    os.makedirs(os.path.dirname(out), exist_ok=True)

    old = None
    if os.path.exists(out):
        old = pd.read_csv(out)
        if len(old):
            resume = datetime.fromtimestamp(int(old["time"].max()), tz=timezone.utc)
            if resume > start:
                start = resume
                print(f"기존 파일 {len(old):,}봉, {resume:%Y-%m-%d %H:%M} 이후만 이어받음")

    print(f"{a.symbol} {a.interval}  {start:%Y-%m-%d} ~ {end:%Y-%m-%d}")
    df = fetch(a.symbol, a.interval, int(start.timestamp() * 1000), int(end.timestamp() * 1000))
    if old is not None and len(old):
        df = pd.concat([old, df]).drop_duplicates("time").sort_values("time")
    df.to_csv(out, index=False)
    print(f"저장: {os.path.relpath(out)}  ({len(df):,}봉, {datetime.fromtimestamp(int(df.time.min()), tz=timezone.utc):%Y-%m-%d} ~ {datetime.fromtimestamp(int(df.time.max()), tz=timezone.utc):%Y-%m-%d})")


if __name__ == "__main__":
    main()
