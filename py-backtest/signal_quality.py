"""지표 신호 품질 분석

tv-api/src/dump-study.js 가 저장한 study_*.csv 를 읽어, 값이 0이 아닌 봉을 "신호 발생"으로 보고
각 신호 열에 대해 N봉 뒤 수익률·적중률·MFE/MAE 를 계산한다.

사용:
    python signal_quality.py ../tv-api/reports/study_ATH_PRO_Final_v4_4_BYBIT_BTCUSDT_P_5m_latest.csv
    python signal_quality.py <csv> --horizons 3,6,12,24 --min-events 5
    python signal_quality.py <csv> --cols "_LONG,_SHORT"          # 특정 열만

열 이름에 LONG/SHORT 가 있으면 방향을 그쪽으로 잡고, 없으면 롱 기준 수익률을 그대로 보여준다
(음수면 숏 신호일 가능성).
"""
import argparse
import glob
import sys

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")  # 윈도우 콘솔 한글 깨짐 방지

PRICE_COLS = {"time", "open", "high", "low", "close", "volume"}


def load_many(patterns: list[str]) -> pd.DataFrame:
    """여러 study_*.csv (구간별 덤프)를 시간순으로 합치고 겹치는 봉은 한 번만 남긴다."""
    files = sorted({f for p in patterns for f in glob.glob(p)})
    if not files:
        sys.exit(f"CSV 를 찾지 못했습니다: {patterns}")
    frames = [pd.read_csv(f) for f in files]
    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates(subset="time").sort_values("time").reset_index(drop=True)
    print(f"파일 {len(files)}개 병합")
    return df
FEE_ROUND_TRIP = 0.0008  # 테이커 0.04% × 2 (참고용)


def direction_of(col: str) -> int:
    u = col.upper()
    if "SHORT" in u:
        return -1
    if "LONG" in u:
        return 1
    return 1  # 알 수 없음: 롱 기준으로 계산 (결과 부호로 판단)


def analyze(df: pd.DataFrame, col: str, horizons: list[int]) -> dict | None:
    v = pd.to_numeric(df[col], errors="coerce").fillna(0)
    events = df.index[(v != 0) & (v.abs() < 1e50)]
    if len(events) == 0:
        return None
    d = direction_of(col)
    close = df["close"].to_numpy(dtype=float)
    high = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    n = len(df)
    out = {"col": col, "dir": "SHORT" if d < 0 else "LONG?", "events": int(len(events))}
    for h in horizons:
        rets, mfe, mae = [], [], []
        for i in events:
            if i + h >= n:
                continue
            entry = close[i]
            fwd = (close[i + h] / entry - 1) * d
            path_h = high[i + 1:i + h + 1]
            path_l = low[i + 1:i + h + 1]
            if d > 0:
                best = (path_h.max() / entry - 1)
                worst = (path_l.min() / entry - 1)
            else:
                best = (1 - path_l.min() / entry)
                worst = (1 - path_h.max() / entry)
            rets.append(fwd)
            mfe.append(best)
            mae.append(worst)
        if not rets:
            continue
        r = np.array(rets)
        out[f"n{h}"] = len(r)
        out[f"avg{h}"] = r.mean() * 100
        out[f"med{h}"] = np.median(r) * 100
        out[f"hit{h}"] = (r > 0).mean() * 100
        out[f"hitfee{h}"] = (r > FEE_ROUND_TRIP).mean() * 100
        out[f"mfe{h}"] = np.mean(mfe) * 100
        out[f"mae{h}"] = np.mean(mae) * 100
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="+", help="study_*.csv (글롭 가능, 여러 개면 병합)")
    ap.add_argument("--horizons", default="3,6,12,24")
    ap.add_argument("--min-events", type=int, default=5)
    ap.add_argument("--cols", default=None, help="쉼표로 구분한 열 이름 (기본: 모든 신호형 열)")
    ap.add_argument("--exclude", default="_H_,_L_", help="이름에 이 문자열이 있으면 제외 (쉼표 구분)")
    a = ap.parse_args()

    df = load_many(a.csv)
    # 리플레이 덤프에는 가격이 비는 봉이 섞일 수 있음 → 앞 값으로 채움 (신호 열은 그대로)
    for c in ("open", "high", "low", "close"):
        df[c] = pd.to_numeric(df[c], errors="coerce").ffill().bfill()
    horizons = [int(x) for x in a.horizons.split(",")]
    excludes = [e for e in a.exclude.split(",") if e]
    if a.cols:
        cols = [c.strip() for c in a.cols.split(",")]
    else:
        # 신호형 열: 숫자이고, 값의 대부분이 0 (가격 레벨·colorer·구름대 제외)
        cols = []
        for c in df.columns:
            if c in PRICE_COLS or c.endswith("_colorer") or any(e in c for e in excludes):
                continue
            v = pd.to_numeric(df[c], errors="coerce")
            if v.notna().sum() == 0:
                continue
            zero_ratio = (v.fillna(0) == 0).mean()
            if zero_ratio >= 0.8:
                cols.append(c)

    first = pd.to_datetime(df["time"].iloc[0], unit="s")
    last = pd.to_datetime(df["time"].iloc[-1], unit="s")
    print(f"봉 {len(df)}개  {first:%Y-%m-%d %H:%M} ~ {last:%Y-%m-%d %H:%M}   (수익률 %, 수수료 왕복 {FEE_ROUND_TRIP*100:.2f}% 참고)\n")

    rows = []
    for c in cols:
        r = analyze(df, c, horizons)
        if r and r["events"] >= a.min_events:
            rows.append(r)
    if not rows:
        print("신호형 열이 없거나 이벤트가 너무 적습니다. --cols 로 열을 지정하거나 --min-events 를 낮추세요.")
        print("열 목록:", ", ".join(df.columns))
        sys.exit(0)

    rows.sort(key=lambda r: -r["events"])
    head = f"{'열':<16}{'방향':<7}{'건수':>5}"
    for h in horizons:
        head += f" | {h:>2}봉 평균  적중  적중(수수료후)  MFE   MAE"
    print(head)
    for r in rows:
        line = f"{r['col']:<16}{r['dir']:<7}{r['events']:>5}"
        for h in horizons:
            if f"n{h}" not in r:
                line += " | " + " " * 40
                continue
            line += f" | {r[f'avg{h}']:>+7.3f} {r[f'hit{h}']:>5.0f}% {r[f'hitfee{h}']:>8.0f}%    {r[f'mfe{h}']:>+5.2f} {r[f'mae{h}']:>+5.2f}"
        print(line)


if __name__ == "__main__":
    main()
