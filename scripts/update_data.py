#!/usr/bin/env python3
from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "dashboard_data.json"


def get_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def clamp(v: float, lo: float = 0.0, hi: float = 10.0):
    return max(lo, min(hi, v))


def signal(s: float):
    return "청신호" if s >= 6.5 else ("관망" if s >= 3.5 else "적신호")


def pct(a: float, b: float):
    return (a / b - 1.0) * 100.0


def main():
    # 7일 차트 (4h)
    btc_kl = get_json("https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=4h&limit=42")
    eth_kl = get_json("https://api.binance.com/api/v3/klines?symbol=ETHUSDT&interval=4h&limit=42")
    btc_chart = [[k[0], float(k[4])] for k in btc_kl]
    eth_chart = [[k[0], float(k[4])] for k in eth_kl]

    fear = float(get_json("https://api.alternative.me/fng/?limit=1")["data"][0]["value"])
    p_b = get_json("https://fapi.binance.com/fapi/v1/premiumIndex?symbol=BTCUSDT")
    p_e = get_json("https://fapi.binance.com/fapi/v1/premiumIndex?symbol=ETHUSDT")
    oi = get_json("https://fapi.binance.com/futures/data/openInterestHist?symbol=BTCUSDT&period=1d&limit=2")
    taker = get_json("https://fapi.binance.com/futures/data/takerlongshortRatio?symbol=BTCUSDT&period=1d&limit=2")
    ethbtc = get_json("https://api.binance.com/api/v3/klines?symbol=ETHBTC&interval=1d&limit=31")
    btc1d = get_json("https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=8")
    eth1d = get_json("https://api.binance.com/api/v3/klines?symbol=ETHUSDT&interval=1d&limit=31")

    closes_ethbtc = [float(k[4]) for k in ethbtc]
    ethbtc7 = pct(closes_ethbtc[-1], closes_ethbtc[-8])
    ethbtc30 = pct(closes_ethbtc[-1], closes_ethbtc[0])

    closes_btc = [float(k[4]) for k in btc1d]
    closes_eth = [float(k[4]) for k in eth1d]
    btc7 = pct(closes_btc[-1], closes_btc[0])
    eth7 = pct(closes_eth[-1], closes_eth[-8])
    eth30 = pct(closes_eth[-1], closes_eth[0])

    favg = (float(p_b["lastFundingRate"]) * 100 + float(p_e["lastFundingRate"]) * 100) / 2
    oichg = pct(float(oi[1]["sumOpenInterestValue"]), float(oi[0]["sumOpenInterestValue"]))
    ratio = float(taker[-1]["buySellRatio"])
    ratio_prev = float(taker[-2]["buySellRatio"])
    ratio_chg = pct(ratio, ratio_prev)

    indicators = []

    def add(name, s, reason, comment):
        indicators.append({"name": name, "score": round(s, 1), "signal": signal(s), "reason": reason, "comment": comment})

    add("유동성(프록시)", clamp(5 + (-favg) * 80), f"평균 펀딩 {favg:+.4f}%", "펀딩 중립/음수는 과열 완화로 유동성 환경이 상대적으로 안정적")
    add("BTC 도미넌스 구조(프록시)", clamp(5 - ethbtc7 / 1.5), f"ETH/BTC 7D {ethbtc7:+.2f}%", "ETH/BTC 약세면 BTC 쏠림 국면 가능성")
    add("ETH/BTC 상대강도(7D)", clamp(5 + ethbtc7 / 1.2), f"ETH/BTC 7D {ethbtc7:+.2f}%, 30D {ethbtc30:+.2f}%", "ETH 상대강도 핵심")
    add("시장 모멘텀(프록시)", clamp(5 + btc7 / 2), f"BTC 7D {btc7:+.2f}%", "코어 자산 모멘텀")
    add("펀딩 과열도(BTC/ETH)", clamp(10 - abs(favg - 0.005) * 120), f"평균 펀딩 {favg:+.4f}%", "과열/청산 리스크")
    add("미결제약정 안정성(OI)", clamp(10 - abs(oichg) * 0.7), f"OI {oichg:+.2f}%", "레버리지 압력")
    add("테이커 수급 균형", clamp(10 - abs(ratio - 1.04) * 40 - abs(ratio_chg) * 0.2), f"비율 {ratio:.3f}, 전일 {ratio_chg:+.2f}%", "매수/매도 쏠림")
    add("시장 심리(F&G)", clamp(fear / 10), f"F&G {fear:.0f}/100", "극단 심리 구간")
    add("BTC 추세 모멘텀(7D)", clamp(5 + btc7 / 2), f"BTC 7D {btc7:+.2f}%", "코어 추세")
    add("ETH 절대+상대 모멘텀", clamp(5 + eth7 / 2 + ethbtc7 / 4), f"ETH 7D {eth7:+.2f}%, 30D {eth30:+.2f}%", "ETH 운용 난이도")

    total = round(sum(x["score"] for x in indicators) / len(indicators), 1)

    # 김프
    up_b = get_json("https://api.upbit.com/v1/ticker?markets=KRW-BTC")[0]["trade_price"]
    up_e = get_json("https://api.upbit.com/v1/ticker?markets=KRW-ETH")[0]["trade_price"]
    b_usdt = float(get_json("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT")["price"])
    e_usdt = float(get_json("https://api.binance.com/api/v3/ticker/price?symbol=ETHUSDT")["price"])
    usdkrw = get_json("https://open.er-api.com/v6/latest/USD")["rates"]["KRW"]

    fair_b = b_usdt * usdkrw
    fair_e = e_usdt * usdkrw

    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total": total,
            "signal": signal(total),
            "green": len([x for x in indicators if x["signal"] == "청신호"]),
            "red": len([x for x in indicators if x["signal"] == "적신호"]),
        },
        "kimchi": {
            "usdkrw": usdkrw,
            "btcKrw": up_b,
            "ethKrw": up_e,
            "btcPrem": (up_b / fair_b - 1) * 100,
            "ethPrem": (up_e / fair_e - 1) * 100,
        },
        "charts": {"btc": btc_chart, "eth": eth_chart},
        "indicators": indicators,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("updated", OUT)


if __name__ == "__main__":
    main()
