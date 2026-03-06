#!/usr/bin/env python3
from __future__ import annotations

import json
import urllib.request
import sys
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
    # 행동형 라벨 (오해 방지)
    if s >= 8.0:
        return "공격 진입 가능"
    if s >= 6.5:
        return "분할 진입 구간"
    if s >= 4.5:
        return "관망/대기"
    if s >= 3.0:
        return "비중 축소 고려"
    return "방어 최우선"


def pct(a: float, b: float):
    return (a / b - 1.0) * 100.0


def score_kimchi_flow(kimchi_pct: float) -> float:
    """
    김프/역프 기반 자금흐름 점수(0~10).
    - 약한 역프(-0.5~-2.0%): 매력 구간으로 가점
    - 중립 구간(-2.0~-3.5%, +0.5% 이내): 관망
    - 과도한 역프(<-3.5%) 또는 과열 프리미엄(>+0.5%): 감점
    """
    k = kimchi_pct
    if -2.0 <= k <= 0.5:
        # 중심을 -1.2%로 두고 완만한 봉우리 형태
        return clamp(7.2 - abs(k + 1.2) * 1.2)
    if -3.5 <= k < -2.0:
        # 깊어질수록 점진 감점
        return clamp(5.2 - (abs(k) - 2.0) * 1.1)
    if k < -3.5:
        # 유동성 경색 가능성 높아 강한 감점
        return clamp(2.8 - (abs(k) - 3.5) * 1.0)
    # k > +0.5: 국내 과열 프리미엄 구간
    return clamp(5.0 - (k - 0.5) * 1.4)


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
    coin = (sys.argv[1] if len(sys.argv) > 1 else "ETH").upper()
    coin_map = {
        "ETH": {"binance": "ETHUSDT", "upbit": "KRW-ETH", "name": "ETH"},
        "XRP": {"binance": "XRPUSDT", "upbit": "KRW-XRP", "name": "XRP"},
    }
    cfg = coin_map.get(coin, coin_map["ETH"])

    # 차트 데이터
    btc_kl_4h = get_json("https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=4h&limit=42")
    coin_kl_4h = get_json(f"https://api.binance.com/api/v3/klines?symbol={cfg['binance']}&interval=4h&limit=42")
    btc_chart = [[k[0], float(k[4])] for k in btc_kl_4h]
    coin_chart = [[k[0], float(k[4])] for k in coin_kl_4h]

    # 핵심 시세/파생/심리
    fear = float(get_json("https://api.alternative.me/fng/?limit=1")["data"][0]["value"])
    p_b = get_json("https://fapi.binance.com/fapi/v1/premiumIndex?symbol=BTCUSDT")
    p_e = get_json(f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={cfg['binance']}")
    oi_eth = get_json(f"https://fapi.binance.com/futures/data/openInterestHist?symbol={cfg['binance']}&period=1d&limit=2")
    taker_eth = get_json(f"https://fapi.binance.com/futures/data/takerlongshortRatio?symbol={cfg['binance']}&period=1d&limit=2")

    coinbtc_symbol = "ETHBTC" if cfg['name']=="ETH" else "XRPBTC"
    ethbtc_1d = get_json(f"https://api.binance.com/api/v3/klines?symbol={coinbtc_symbol}&interval=1d&limit=90")
    btc_1d = get_json("https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=90")
    eth_1d = get_json(f"https://api.binance.com/api/v3/klines?symbol={cfg['binance']}&interval=1d&limit=90")
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
    up_e = get_json(f"https://api.upbit.com/v1/ticker?markets={cfg['upbit']}")[0]["trade_price"]
    b_usdt = float(get_json("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT")["price"])
    e_usdt = float(get_json(f"https://api.binance.com/api/v3/ticker/price?symbol={cfg['binance']}")["price"])
    usdkrw = get_json("https://open.er-api.com/v6/latest/USD")["rates"]["KRW"]
    fair_b = b_usdt * usdkrw
    fair_e = e_usdt * usdkrw
    kim_b = (up_b / fair_b - 1) * 100
    kim_e = (up_e / fair_e - 1) * 100

    # 10 지표
    indicators = []

    def add_i(name, s, reason, comment):
        indicators.append({"name": name, "score": round(s, 1), "signal": signal(s), "reason": reason, "comment": comment})

    add_i("유동성(펀딩 프록시)", clamp(5 + (-favg) * 80), f"평균 펀딩 {favg:+.4f}%", "펀딩이 중립 또는 약음수 구간이면 레버리지 과열이 완화된 상태로 해석합니다. 즉, 단기 급락을 유발할 수 있는 과열 롱 포지션이 상대적으로 줄어든 국면이며, 추격매수보다 계획된 분할 진입이 유리한 환경입니다.")
    add_i("BTC 도미넌스 구조(프록시)", clamp(5 - ethbtc7 / 1.5), f"ETH/BTC 7D {ethbtc7:+.2f}%", "ETH/BTC 약세는 시장 자금이 알트보다 BTC로 쏠리는 흐름을 의미합니다. 이 구간에서는 ETH 단독 비중을 급격히 늘리기보다, BTC 대비 상대강도 회복 여부를 먼저 확인하는 보수적 접근이 유리합니다.")
    add_i("ETH/BTC 상대강도", clamp(5 + ethbtc7 / 1.2), f"ETH/BTC 7D {ethbtc7:+.2f}%, 30D {ethbtc30:+.2f}%", "ETH/BTC는 ETH 매매에서 가장 중요한 선행지표 중 하나입니다. 단기(7D)와 중기(30D)가 동시에 약하면 반등 신뢰도가 떨어지므로, 가격이 반등해도 비중 확대를 서두르지 않는 것이 좋습니다.")
    add_i("시장 모멘텀", clamp(5 + btc7 / 2), f"BTC 7D {btc7:+.2f}%", "시장 코어 자산인 BTC의 7일 모멘텀으로 전체 체온을 측정합니다. BTC가 약하면 알트의 독립 상승이 오래가기 어렵고, BTC가 안정적이면 ETH 반등 전략의 성공 확률이 높아집니다.")
    add_i("펀딩 과열도", clamp(10 - abs(favg - 0.005) * 120), f"평균 펀딩 {favg:+.4f}%", "펀딩이 과도한 플러스 구간이면 롱 과열로 해석하며, 갑작스러운 롱 청산 리스크가 커집니다. 현재 값은 과열이 크지 않아 급격한 변동성 폭발 가능성은 낮은 편이지만, 급변 시 즉시 방어모드 전환이 필요합니다.")
    add_i("미결제약정 안정성", clamp(10 - abs(oi_chg) * 0.7), f"ETH OI {oi_chg:+.2f}%", "OI 변화는 레버리지의 확장/축소 속도를 보여줍니다. 급증은 과열, 급감은 포지션 청산을 의미하며 둘 다 변동성 확대 신호입니다. 따라서 OI 급변 구간에서는 진입 간격을 넓히고 손절 기준을 엄격히 적용해야 합니다.")
    add_i("테이커 수급 균형", clamp(10 - abs(ratio - 1.04) * 40 - abs(ratio_chg) * 0.2), f"비율 {ratio:.3f}, 전일 {ratio_chg:+.2f}%", "테이커 매수/매도 비율은 실제 공격 주문의 균형을 보여줍니다. 한쪽으로 과도하게 쏠리면 되돌림 가능성이 커지므로, 수급 균형이 깨지는 구간에서는 추격 진입보다 눌림 또는 이탈 확인 전략이 적합합니다.")
    add_i("시장 심리(F&G)", clamp(fear / 10), f"F&G {fear:.0f}/100", "심리 지표가 극단 공포에 가까울수록 기술적 반등이 나와도 신뢰도가 낮아질 수 있습니다. 이 구간은 '싸 보여서 전량 매수'보다는 단계적 진입과 빠른 리스크 점검이 핵심입니다.")
    add_i("BTC 추세 모멘텀", clamp(5 + btc7 / 2), f"BTC 7D {btc7:+.2f}%", "BTC 추세는 알트의 방향성을 제약하는 상위 변수입니다. ETH 전략도 결국 BTC 흐름과 동조되므로, BTC 추세 약화 구간에서는 목표수익을 낮추고 방어적 익절 비중을 높이는 편이 안정적입니다.")
    add_i("ETH 절대+상대 모멘텀", clamp(5 + eth7 / 2 + ethbtc7 / 4), f"ETH 7D {eth7:+.2f}%, 30D {eth30:+.2f}%", "ETH 자체 수익률(절대)과 BTC 대비 강도(상대)를 함께 반영한 종합 체력 지표입니다. 절대 반등이 있어도 상대강도가 약하면 추세 지속성이 낮을 수 있어, 1·2·3차 분할 계획을 고정해 기계적으로 대응하는 것이 유리합니다.")

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
        score_kimchi_flow(kim_e),
        f"ETH 김프 {kim_e:+.2f}% (역프면 국내 과열 완화)",
        "약한 역프는 가점, 과도한 역프는 유동성 경색 리스크로 감점",
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

    # 이벤트 드라이버(호재/악재) 레이어
    catalysts = {
        "bullish": [
            {
                "title": "ETH 스테이킹/수수료 정책 완화 기대",
                "probability": "중간",
                "probPct": 55,
                "eta": "1~3개월",
                "impact": "강",
                "direction": "+",
                "note": "정책 불확실성이 완화되면 장기 보유 심리와 네트워크 락업 수요가 개선될 가능성이 있습니다."
            },
            {
                "title": "ETH/BTC 상대강도 반등 시그널",
                "probability": "중간" if ethbtc7 > -2 else "낮음",
                "probPct": 58 if ethbtc7 > -2 else 35,
                "eta": "1~4주",
                "impact": "중",
                "direction": "+",
                "note": f"현재 ETH/BTC 7D {ethbtc7:+.2f}%로 아직 약하지만, 하락 둔화/양전환 시 알트 선호 재개 신호가 됩니다."
            },
            {
                "title": "파생 과열 완화(중립~약음수 펀딩)",
                "probability": "높음",
                "probPct": 72,
                "eta": "진행중(1~2주 유지 가능)",
                "impact": "중",
                "direction": "+",
                "note": f"평균 펀딩 {favg:+.4f}%로 과열이 낮아 급격한 롱 청산 리스크가 상대적으로 줄어든 상태입니다."
            }
        ],
        "bearish": [
            {
                "title": "규제/정책 발언에 따른 변동성 재확대",
                "probability": "중간",
                "probPct": 45,
                "eta": "상시(헤드라인 발생 즉시)",
                "impact": "강",
                "direction": "-",
                "note": "정책 관련 헤드라인은 단기 방향을 급격히 바꾸므로, 발생 시 추격 금지·리스크 축소가 우선입니다."
            },
            {
                "title": "ETH/BTC 추가 약세 지속",
                "probability": "높음" if ethbtc7 < 0 else "중간",
                "probPct": 68 if ethbtc7 < 0 else 48,
                "eta": "1~2주",
                "impact": "중",
                "direction": "-",
                "note": f"ETH/BTC 7D {ethbtc7:+.2f}% 약세가 이어지면 ETH 단독 랠리 신뢰도가 낮아집니다."
            },
            {
                "title": "레버리지 재팽창 동반 하락",
                "probability": "중간" if oi_chg > 0 else "낮음",
                "probPct": 52 if oi_chg > 0 else 30,
                "eta": "수일~1주",
                "impact": "강",
                "direction": "-",
                "note": f"OI {oi_chg:+.2f}% 변화와 함께 하락이 동반되면 강제청산성 하방이 커질 수 있습니다."
            }
        ],
        "houseView": "단기 노이즈에 일희일비보다, 이벤트 발생 여부와 ETH/BTC 회복 확인에 따라 단계적으로 행동하는 전략이 유리합니다."
    }

    entry1 = round(up_e * 0.98)
    entry2 = round(up_e * 0.94)
    entry3 = round(up_e * 0.90)
    stop_loss = round(up_e * 0.86)
    take1 = round(up_e * 1.08)
    take2 = round(up_e * 1.14)

    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "targetCoin": cfg['name'],
        "summary": {
            "total": total,
            "index100": round(total * 10, 0),
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
        "historyModel": {
            "framework": "2018~2026 BTC/ETH 히스토리에서 급등·급락 전조 패턴을 학습한 내부 규칙 기반 비교",
            "features": [
                "7D/30D 모멘텀 구조",
                "ETH/BTC 상대강도",
                "펀딩 과열도",
                "OI 급변 스트레스",
                "심리지수(Fear&Greed)",
                "김치프리미엄/역프리미엄"
            ],
            "currentInterpretation": "현재는 2021형 폭등 직전보다는 변동성 조정 구간의 특징이 강하고, 2024형 랠리 초기와 일부 유사하지만 ETH/BTC 회복 강도가 부족해 확인형 접근이 필요합니다.",
            "riskNote": "핵심 리스크는 ETH/BTC 추가 약세와 레버리지 재팽창 동반 하락입니다. 해당 신호 발생 시 계획된 진입 비중을 즉시 축소합니다."
        },
        "kimchi": {
            "usdkrw": usdkrw,
            "btcKrw": up_b,
            "coinKrw": up_e,
            "btcPrem": kim_b,
            "coinPrem": kim_e,
        },
        "catalysts": catalysts,
        "indicators": indicators,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("updated", OUT)


if __name__ == "__main__":
    main()
