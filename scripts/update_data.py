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


def recommendation(s: float):
    if s >= 8.0:
        return "매수적극추천"
    if s >= 6.5:
        return "매수추천"
    if s >= 4.5:
        return "관망"
    if s >= 3.0:
        return "매도추천"
    return "매도적극추천"


def pct(a: float, b: float):
    return (a / b - 1.0) * 100.0


def kline_close(kl):
    return [float(k[4]) for k in kl]


def find_history_regimes(btc_daily):
    closes = kline_close(btc_daily)
    times = [int(k[0]) for k in btc_daily]
    windows = []

    # 30일 수익률 기준으로 과거 급등/급락 국면 탐색
    for i in range(30, len(closes)):
        r30 = pct(closes[i], closes[i - 30])
        windows.append((i, r30))

    top_bull = sorted(windows, key=lambda x: x[1], reverse=True)[:3]
    top_bear = sorted(windows, key=lambda x: x[1])[:3]

    def to_regime(item, tag):
        i, r = item
        dt = datetime.fromtimestamp(times[i] / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        return {"date": dt, "return30d": round(r, 2), "type": tag}

    return [to_regime(x, "bull") for x in top_bull] + [to_regime(x, "bear") for x in top_bear]


def main():
    # 차트 데이터
    btc_kl_4h = get_json("https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=4h&limit=42")
    eth_kl_4h = get_json("https://api.binance.com/api/v3/klines?symbol=ETHUSDT&interval=4h&limit=42")
    btc_chart = [[k[0], float(k[4])] for k in btc_kl_4h]
    eth_chart = [[k[0], float(k[4])] for k in eth_kl_4h]

    # 핵심 시세/파생/심리
    fear = float(get_json("https://api.alternative.me/fng/?limit=1")["data"][0]["value"])
    p_b = get_json("https://fapi.binance.com/fapi/v1/premiumIndex?symbol=BTCUSDT")
    p_e = get_json("https://fapi.binance.com/fapi/v1/premiumIndex?symbol=ETHUSDT")
    oi_eth = get_json("https://fapi.binance.com/futures/data/openInterestHist?symbol=ETHUSDT&period=1d&limit=2")
    taker_eth = get_json("https://fapi.binance.com/futures/data/takerlongshortRatio?symbol=ETHUSDT&period=1d&limit=2")

    ethbtc_1d = get_json("https://api.binance.com/api/v3/klines?symbol=ETHBTC&interval=1d&limit=90")
    btc_1d = get_json("https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=90")
    eth_1d = get_json("https://api.binance.com/api/v3/klines?symbol=ETHUSDT&interval=1d&limit=90")
    btc_1d_long = get_json("https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=1000")

    c_eb = kline_close(ethbtc_1d)
    c_b = kline_close(btc_1d)
    c_e = kline_close(eth_1d)

    ethbtc7 = pct(c_eb[-1], c_eb[-8])
    ethbtc30 = pct(c_eb[-1], c_eb[-31])
    btc7 = pct(c_b[-1], c_b[-8])
    eth7 = pct(c_e[-1], c_e[-8])
    eth30 = pct(c_e[-1], c_e[-31])

    favg = (float(p_b["lastFundingRate"]) + float(p_e["lastFundingRate"])) / 2 * 100
    oi_chg = pct(float(oi_eth[1]["sumOpenInterestValue"]), float(oi_eth[0]["sumOpenInterestValue"]))
    ratio = float(taker_eth[-1]["buySellRatio"])
    ratio_prev = float(taker_eth[-2]["buySellRatio"])
    ratio_chg = pct(ratio, ratio_prev)

    # 김프
    up_b = get_json("https://api.upbit.com/v1/ticker?markets=KRW-BTC")[0]["trade_price"]
    up_e = get_json("https://api.upbit.com/v1/ticker?markets=KRW-ETH")[0]["trade_price"]
    b_usdt = float(get_json("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT")["price"])
    e_usdt = float(get_json("https://api.binance.com/api/v3/ticker/price?symbol=ETHUSDT")["price"])
    usdkrw = get_json("https://open.er-api.com/v6/latest/USD")["rates"]["KRW"]
    fair_b = b_usdt * usdkrw
    fair_e = e_usdt * usdkrw
    kim_b = (up_b / fair_b - 1) * 100
    kim_e = (up_e / fair_e - 1) * 100

    # 10 지표
    indicators = []

    def add_i(name, s, reason, comment):
        indicators.append({"name": name, "score": round(s, 1), "signal": signal(s), "reason": reason, "comment": comment})

    add_i("유동성(펀딩 프록시)", clamp(5 + (-favg) * 80), f"평균 펀딩 {favg:+.4f}%", "펀딩 중립/음수는 과열 완화")
    add_i("BTC 도미넌스 구조(프록시)", clamp(5 - ethbtc7 / 1.5), f"ETH/BTC 7D {ethbtc7:+.2f}%", "ETH 약세면 BTC 선호")
    add_i("ETH/BTC 상대강도", clamp(5 + ethbtc7 / 1.2), f"ETH/BTC 7D {ethbtc7:+.2f}%, 30D {ethbtc30:+.2f}%", "ETH 핵심 선행지표")
    add_i("시장 모멘텀", clamp(5 + btc7 / 2), f"BTC 7D {btc7:+.2f}%", "시장 체온")
    add_i("펀딩 과열도", clamp(10 - abs(favg - 0.005) * 120), f"평균 펀딩 {favg:+.4f}%", "급청산 리스크")
    add_i("미결제약정 안정성", clamp(10 - abs(oi_chg) * 0.7), f"ETH OI {oi_chg:+.2f}%", "레버리지 쏠림")
    add_i("테이커 수급 균형", clamp(10 - abs(ratio - 1.04) * 40 - abs(ratio_chg) * 0.2), f"비율 {ratio:.3f}, 전일 {ratio_chg:+.2f}%", "롱/숏 균형")
    add_i("시장 심리(F&G)", clamp(fear / 10), f"F&G {fear:.0f}/100", "극단 심리")
    add_i("BTC 추세 모멘텀", clamp(5 + btc7 / 2), f"BTC 7D {btc7:+.2f}%", "코어 추세")
    add_i("ETH 절대+상대 모멘텀", clamp(5 + eth7 / 2 + ethbtc7 / 4), f"ETH 7D {eth7:+.2f}%, 30D {eth30:+.2f}%", "실전 ETH 체력")

    total = round(sum(x["score"] for x in indicators) / len(indicators), 1)

    # 전문가 위원회 8개 그룹
    desks = []

    def add_desk(name, score, thesis, action):
        desks.append(
            {
                "name": name,
                "score": round(score, 1),
                "signal": signal(score),
                "recommendation": recommendation(score),
                "thesis": thesis,
                "action": action,
            }
        )

    add_desk(
        "Regime Desk",
        clamp((5 + btc7 / 2 + fear / 20) / 2),
        f"시장 국면은 {'회복 초입' if btc7 > 0 else '리스크오프'} 성격. Fear&Greed={fear:.0f}",
        "공격 진입보다 확인형 분할",
    )
    add_desk(
        "Macro Liquidity Desk",
        clamp(5 + (-favg) * 60 - max(0, kim_b) * 0.2),
        f"펀딩 {favg:+.4f}%, BTC 김프 {kim_b:+.2f}%",
        "유동성 과열은 낮아 추격보다 눌림 대기",
    )
    add_desk(
        "On-chain/Flow Desk",
        clamp(5 + kim_e * 0.4 + (0.5 - abs(kim_e)) * 2),
        f"ETH 김프 {kim_e:+.2f}% (역프면 국내 과열 완화)",
        "역프 구간은 단기 반등 가능성 체크",
    )
    add_desk(
        "Derivatives Desk",
        clamp(10 - abs(favg - 0.005) * 120 - abs(oi_chg) * 0.15),
        f"펀딩 {favg:+.4f}%, ETH OI {oi_chg:+.2f}%",
        "과열 낮음. 다만 OI 급변시 레버리지 축소",
    )
    add_desk(
        "Technical Structure Desk",
        clamp(5 + eth7 / 2 + eth30 / 8),
        f"ETH 7D {eth7:+.2f}%, 30D {eth30:+.2f}%",
        "단기 반등보다 추세 확인형 매수",
    )
    add_desk(
        "Relative Value Desk",
        clamp(5 + ethbtc7 / 1.2),
        f"ETH/BTC 7D {ethbtc7:+.2f}%",
        "ETH/BTC 반등 전까지 ETH 비중 과확대 금지",
    )
    add_desk(
        "Event/Narrative Desk",
        clamp(5 + (fear - 50) / 25),
        f"심리지수 {fear:.0f} (이벤트 민감도 높음)",
        "헤드라인 장세 가능성, 이벤트 캘린더 필수",
    )
    add_desk(
        "Risk Control Desk",
        clamp(10 - abs(ratio - 1.0) * 20 - max(0, -eth7) * 0.15),
        f"테이커비 {ratio:.3f}, ETH7D {eth7:+.2f}%",
        "분할진입 20/30/50, 무효화 조건 엄수",
    )

    committee_score = round(sum(d["score"] for d in desks) / len(desks), 1)

    # 과거 유사 국면 비교 (사용자가 언급한 2021/2024 포함)
    history = find_history_regimes(btc_1d_long)

    current_vector = [btc7, eth7, ethbtc7, favg, oi_chg, fear]

    # 2021, 2024 대표 포인트 찾아 간단 비교
    tagged = []
    for h in history:
        y = int(h["date"][:4])
        if y in (2021, 2024):
            tagged.append(h)

    tagged = sorted(tagged, key=lambda x: abs(x["return30d"]), reverse=True)[:4]

    history_summary = []
    for h in tagged:
        label = "폭등" if h["return30d"] > 0 else "폭락"
        history_summary.append(
            {
                "year": h["date"][:4],
                "date": h["date"],
                "type": label,
                "return30d": h["return30d"],
                "note": f"{h['date']} 전후 30일 {h['return30d']:+.2f}% 구간",
            }
        )

    final_decision = (
        "확인형 분할매수" if committee_score >= 5.0 else "관망 및 비중관리"
    )

    entry1 = round(up_e * 0.98)
    entry2 = round(up_e * 0.94)
    entry3 = round(up_e * 0.90)
    stop_loss = round(up_e * 0.86)
    take1 = round(up_e * 1.08)
    take2 = round(up_e * 1.14)

    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "targetCoin": "ETH",
        "summary": {
            "total": total,
            "signal": signal(total),
            "green": len([x for x in indicators if x["signal"] == "청신호"]),
            "red": len([x for x in indicators if x["signal"] == "적신호"]),
        },
        "committee": {
            "score": committee_score,
            "signal": signal(committee_score),
            "decision": final_decision,
            "tradePlan": {
                "currentPrice": up_e,
                "entry1": {"price": entry1, "allocation": "20%"},
                "entry2": {"price": entry2, "allocation": "30%"},
                "entry3": {"price": entry3, "allocation": "50%"},
                "stopLoss": stop_loss,
                "takeProfit1": take1,
                "takeProfit2": take2,
            },
            "invalidations": ["ETH/BTC 추가 하락 지속", "BTC 급락 + OI 급증 동반"],
            "desks": desks,
        },
        "historyComparisons": history_summary,
        "kimchi": {
            "usdkrw": usdkrw,
            "btcKrw": up_b,
            "ethKrw": up_e,
            "btcPrem": kim_b,
            "ethPrem": kim_e,
        },
        "indicators": indicators,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("updated", OUT)


if __name__ == "__main__":
    main()
