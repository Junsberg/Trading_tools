"""덤프한 Ultimate 값을 캔들 위에 그려주는 로컬 HTML 차트 뷰어 (봉 수 제한 없음)

사용:
    python viewer.py BTCUSDT --tf 5                 # 5분봉 덤프 전체
    python viewer.py BTCUSDT --tf 1 --days 30       # 1분봉 최근 30일
    python viewer.py ETHUSDT --tf 5 --trades my_trades.csv
        my_trades.csv 열: time(YYYY-MM-DD HH:MM, KST), side(long/short), note(선택)

출력: reports/view_<SYM>_<tf>m.html → 브라우저에서 열기 (인터넷 필요: 차트 라이브러리 CDN)
"""
import argparse, glob, json, os, sys
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ap = argparse.ArgumentParser()
ap.add_argument("symbol"); ap.add_argument("--tf", type=int, default=5); ap.add_argument("--days", type=float, default=None)
ap.add_argument("--trades", default=None)
a = ap.parse_args()

pat = f"../tv-api/reports/study_ULT_SQ_BYBIT_{a.symbol}_P_5m_*.csv" if a.tf == 5 else f"../tv-api/reports/study_ULT_BYBIT_{a.symbol}_P_1m_*.csv"
fs = sorted(glob.glob(pat))
if not fs:
    sys.exit(f"덤프 없음: {pat}")
df = pd.concat([pd.read_csv(f) for f in fs]).drop_duplicates("time").sort_values("time").reset_index(drop=True)
for c in ("open", "high", "low", "close", "volume"):
    df[c] = pd.to_numeric(df[c], errors="coerce")
df = df.dropna(subset=["open", "high", "low", "close"])
if a.days:
    df = df[df.time >= df.time.max() - a.days * 86400]
num = lambda c: pd.to_numeric(df[c], errors="coerce").where(lambda v: v.abs() < 1e50) if c in df else pd.Series(float("nan"), index=df.index)

clouds = {}
for k in range(6):
    hi = pd.concat([num(f"_{k}_"), num(f"_{k}__2")], axis=1).max(axis=1); lo = pd.concat([num(f"_{k}_"), num(f"_{k}__2")], axis=1).min(axis=1)
    clouds[k] = [{"time": int(t), "value": round(float(v), 2)} for t, v in zip(df.time, hi) if pd.notna(v)], \
                [{"time": int(t), "value": round(float(v), 2)} for t, v in zip(df.time, lo) if pd.notna(v)]
colors = {0: "#ff2d95", 1: "#FFFFFF", 2: "#00E676", 3: "#FF9800", 4: "#00BCD4", 5: "#E040FB"}

sig_defs = {"__LONG": ("파랑빔 롱", "belowBar", "arrowUp", "#4da3ff"), "__SHORT": ("노랑빔 숏", "aboveBar", "arrowDown", "#ffd54a"),
            "__LONG_2": ("헥사곤 롱", "belowBar", "circle", "#69f0ae"), "__SHORT_2": ("헥사곤 숏", "aboveBar", "circle", "#ff5252")}
markers = []
for col, (label, pos, shape, color) in sig_defs.items():
    v = num(col).fillna(0)
    for t in df.time[v != 0]:
        markers.append({"time": int(t), "position": pos, "shape": shape, "color": color, "text": label})
if a.trades and os.path.exists(a.trades):
    tr = pd.read_csv(a.trades)
    for _, r in tr.iterrows():
        t = int((pd.Timestamp(r["time"]) - pd.Timedelta(hours=9)).timestamp())
        t -= t % (a.tf * 60)
        long = str(r.get("side", "")).lower().startswith("l")
        markers.append({"time": t, "position": "belowBar" if long else "aboveBar", "shape": "square", "color": "#ffffff", "text": f"내 {'롱' if long else '숏'} {r.get('note', '')}"})
markers.sort(key=lambda m: m["time"])

candles = [{"time": int(t), "open": o, "high": h, "low": l, "close": c} for t, o, h, l, c in zip(df.time, df.open, df.high, df.low, df.close)]
first, last = pd.to_datetime(df.time.iloc[0], unit="s") + pd.Timedelta(hours=9), pd.to_datetime(df.time.iloc[-1], unit="s") + pd.Timedelta(hours=9)
title = f"{a.symbol}.P {a.tf}분봉 · ATH Ultimate 구름/신호 · {first:%Y-%m-%d} ~ {last:%Y-%m-%d} (KST) · {len(df):,}봉"

html = f"""<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8"><title>{a.symbol} {a.tf}m 뷰어</title>
<script src="https://cdn.jsdelivr.net/npm/lightweight-charts@4.2.0/dist/lightweight-charts.standalone.production.js"></script>
<style>body{{margin:0;background:#0d1117;color:#c9d1d9;font:13px system-ui}} #bar{{padding:8px 12px;display:flex;gap:14px;align-items:center;flex-wrap:wrap}}
#chart{{height:calc(100vh - 44px)}} label{{cursor:pointer}} .sw{{display:inline-block;width:10px;height:10px;margin-right:4px;vertical-align:middle}}</style></head>
<body><div id="bar"><b>{title}</b>
{"".join(f'<label><input type="checkbox" data-k="{k}" {"checked" if k else ""}><span class="sw" style="background:{colors[k]}"></span>구름{k}</label>' for k in range(6))}
<label><input type="checkbox" id="mk" checked>신호/내 매매</label><span style="opacity:.6">휠=확대 · 드래그=이동 · 시간은 KST</span></div><div id="chart"></div>
<script>
const clouds={json.dumps({k: {"hi": v[0], "lo": v[1]} for k, v in clouds.items()})}; const colors={json.dumps(colors)};
const candles={json.dumps(candles)}; const markers={json.dumps(markers)};
const chart=LightweightCharts.createChart(document.getElementById('chart'),{{layout:{{background:{{color:'#0d1117'}},textColor:'#c9d1d9'}},grid:{{vertLines:{{color:'#161b22'}},horzLines:{{color:'#161b22'}}}},
 timeScale:{{timeVisible:true,secondsVisible:false}},localization:{{timeFormatter:t=>new Date((t+32400)*1000).toISOString().replace('T',' ').slice(0,16)}}}});
chart.timeScale().applyOptions({{tickMarkFormatter:(t,type)=>{{const d=new Date((t+32400)*1000);return type>=3?d.toISOString().slice(11,16):d.toISOString().slice(5,10)}}}});
const cs=chart.addCandlestickSeries({{upColor:'#26a69a',downColor:'#ef5350',wickUpColor:'#26a69a',wickDownColor:'#ef5350',borderVisible:false}}); cs.setData(candles);
const lines={{}};
for(const k in clouds){{lines[k]=[chart.addLineSeries({{color:colors[k],lineWidth:1,priceLineVisible:false,lastValueVisible:false}}),chart.addLineSeries({{color:colors[k],lineWidth:1,priceLineVisible:false,lastValueVisible:false}})];
 lines[k][0].setData(clouds[k].hi); lines[k][1].setData(clouds[k].lo); if(k==='0'){{lines[k].forEach(s=>s.applyOptions({{visible:false}}))}}}}
document.querySelectorAll('input[data-k]').forEach(el=>el.onchange=()=>lines[el.dataset.k].forEach(s=>s.applyOptions({{visible:el.checked}})));
cs.setMarkers(markers); document.getElementById('mk').onchange=e=>cs.setMarkers(e.target.checked?markers:[]);
chart.timeScale().setVisibleLogicalRange({{from:candles.length-400,to:candles.length}});
</script></body></html>"""
out = os.path.join("..", "tv-api", "reports", f"view_{a.symbol}_{a.tf}m.html")
with open(out, "w", encoding="utf-8") as f:
    f.write(html)
print(f"저장: {os.path.abspath(out)}  ({len(df):,}봉, 신호 {len(markers)}개, {os.path.getsize(out)/1e6:.1f} MB)")
