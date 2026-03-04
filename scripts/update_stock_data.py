#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import urllib.request
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "stock_dashboard_data.json"


def get_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def get_csv_rows(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        txt = r.read().decode("utf-8", errors="ignore")
    return list(csv.DictReader(io.StringIO(txt)))


def clamp(v, lo=0.0, hi=10.0):
    return max(lo, min(hi, v))


def signal(s):
    return "청신호" if s >= 6.5 else ("관망" if s >= 3.5 else "적신호")


def recommendation(s):
    if s >= 8.0:
        return "공격 진입 가능"
    if s >= 6.5:
        return "분할 진입 구간"
    if s >= 4.5:
        return "관망/대기"
    if s >= 3.0:
        return "비중 축소 고려"
    return "방어 최우선"


def main():
    symbol = sys.argv[1] if len(sys.argv) > 1 else "005930"
    stock_name = sys.argv[2] if len(sys.argv) > 2 else "KOSPI"

    poll = get_json("https://polling.finance.naver.com/api/realtime?query=SERVICE_INDEX:KOSPI,KOSDAQ&_")
    datas = poll["result"]["areas"][0]["datas"]
    d = {x["cd"]: x for x in datas}
    kospi = float(d["KOSPI"]["cr"])
    kosdaq = float(d["KOSDAQ"]["cr"])

    ndq = get_csv_rows("https://stooq.com/q/d/l/?s=^ndq&i=d")
    spx = get_csv_rows("https://stooq.com/q/d/l/?s=^spx&i=d")
    dji = get_csv_rows("https://stooq.com/q/d/l/?s=^dji&i=d")
    fx = get_csv_rows("https://stooq.com/q/d/l/?s=usdkrw&i=d")

    def chg(rows):
        a = float(rows[-1]["Close"]); b = float(rows[-2]["Close"])
        return (a / b - 1) * 100

    ndq_chg, spx_chg, dji_chg, fx_chg = chg(ndq), chg(spx), chg(dji), chg(fx)

    # target stock price snapshot (Naver fchart)
    fchart_url = f"https://fchart.stock.naver.com/siseJson.nhn?symbol={symbol}&requestType=1&timeframe=day"
    req = urllib.request.Request(fchart_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        raw = r.read().decode("utf-8", errors="ignore")
    rows = [line.strip() for line in raw.splitlines() if line.strip().startswith('["')]
    closes = []
    if rows:
        parsed = [x.strip('[],').replace('"', '').split(',') for x in rows]
        for p in parsed:
            if len(p) >= 5:
                closes.append(float(p[4].strip()))
        last = parsed[-1]
        o = float(last[1].strip())
        current = float(last[4].strip())
        stock_chg = (current / o - 1) * 100 if o else 0.0
    else:
        current = float(get_json("https://api.stock.naver.com/chart/domestic/index/KOSPI/day")[0]["closePrice"])
        stock_chg = kospi
        closes = [current]

    stock5 = ((closes[-1] / closes[-6] - 1) * 100) if len(closes) >= 6 else stock_chg
    stock20 = ((closes[-1] / closes[-21] - 1) * 100) if len(closes) >= 21 else stock_chg

    indicators = []
    def add(name, score, reason, comment):
        indicators.append({"name": name, "score": round(score,1), "signal": signal(score), "reason": reason, "comment": comment})

    add(f"{stock_name} 당일 탄력", clamp(5 + stock_chg / 2), f"{stock_name} {stock_chg:+.2f}%", "개별 종목 당일 모멘텀")
    add(f"{stock_name} 5일 모멘텀", clamp(5 + stock5 / 3), f"5일 {stock5:+.2f}%", "단기 추세 지속성")
    add(f"{stock_name} 20일 모멘텀", clamp(5 + stock20 / 5), f"20일 {stock20:+.2f}%", "중기 추세 방향")
    add("코스피 시장 체온", clamp(5 + kospi / 2), f"코스피 {kospi:+.2f}%", "국내 대형주 위험선호")
    add("코스닥 시장 체온", clamp(5 + kosdaq / 2), f"코스닥 {kosdaq:+.2f}%", "국내 성장주 심리")
    add("나스닥 전일 흐름", clamp(5 + ndq_chg * 1.2), f"나스닥 {ndq_chg:+.2f}%", "글로벌 성장주 프록시")
    add("S&P500 전일 흐름", clamp(5 + spx_chg * 1.3), f"S&P500 {spx_chg:+.2f}%", "광범위 위험자산 선호")
    add("다우 전일 흐름", clamp(5 + dji_chg * 1.3), f"다우 {dji_chg:+.2f}%", "경기민감주 톤")
    add("원/달러 압력", clamp(5 - fx_chg * 3.0), f"USDKRW {fx_chg:+.2f}%", "원화약세는 외국인 수급 부담")
    add("종합 리스크온 점검", clamp(5 + (stock_chg+kospi+kosdaq+ndq_chg)/4), f"혼합 모멘텀 {((stock_chg+kospi+kosdaq+ndq_chg)/4):+.2f}%", "최종 신호 필터")

    total = round(sum(x["score"] for x in indicators)/len(indicators),1)

    desks = []
    def desk(name, score, thesis, action):
        desks.append({"name": name, "score": round(score,1), "signal": signal(score), "recommendation": recommendation(score), "thesis": thesis, "action": action})

    desk("시장 분위기 팀", clamp(5 + (stock_chg+kospi)/3), f"종목/시장 합산 {((stock_chg+kospi)/2):+.2f}%", "시장 급변이면 속도 조절")
    desk("거시/유동성 팀", clamp(5 - fx_chg*2.5), f"원달러 {fx_chg:+.2f}%", "환율 부담 시 방어 우선")
    desk("해외 연동 팀", clamp(5 + (ndq_chg+spx_chg)/2), f"미국 평균 {((ndq_chg+spx_chg)/2):+.2f}%", "미국 약세면 추격 금지")
    desk("변동성 관리 팀", clamp(10 - abs(stock_chg)*0.5 - abs(kosdaq)*0.2), f"종목 {stock_chg:+.2f}% / 코스닥 {kosdaq:+.2f}%", "진입 크기 축소/분할")
    desk("차트/추세 팀", clamp(5 + stock5/3), f"5일 {stock5:+.2f}%, 20일 {stock20:+.2f}%", "추세 확인형 진입")
    desk("섹터/시장 팀", clamp(5 + (kospi+kosdaq)/4), f"시장 체온 K:{kospi:+.2f}/Q:{kosdaq:+.2f}%", "섹터 강약 분리")
    desk("뉴스/이슈 팀", clamp(5 + (spx_chg+dji_chg)/2), f"미국 뉴스 민감도 {((spx_chg+dji_chg)/2):+.2f}%", "헤드라인 장세 경계")
    desk("리스크 관리 팀", clamp(5 - abs(fx_chg)*2 + (1 if ndq_chg>0 else 0)), f"환율 {fx_chg:+.2f}, 나스닥 {ndq_chg:+.2f}", "손절/현금비중 우선")

    committee = round(sum(d["score"] for d in desks)/len(desks),1)

    entry1 = round(current * 0.99, 2)
    entry2 = round(current * 0.96, 2)
    entry3 = round(current * 0.93, 2)
    stop = round(current * 0.90, 2)
    tp1 = round(current * 1.05, 2)
    tp2 = round(current * 1.10, 2)

    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "targetCoin": stock_name,
        "summary": {"total": total, "index100": round(total*10,0), "signal": signal(total), "green": len([x for x in indicators if x["signal"]=="청신호"]), "red": len([x for x in indicators if x["signal"]=="적신호"])},
        "committee": {
            "score": committee,
            "signal": signal(committee),
            "decision": "분할 접근" if committee >= 5 else "관망 및 비중관리",
            "tradePlan": {"currentPrice": current, "entry1": {"price": entry1, "allocation": "20%"}, "entry2": {"price": entry2, "allocation": "30%"}, "entry3": {"price": entry3, "allocation": "50%"}, "stopLoss": stop, "takeProfit1": tp1, "takeProfit2": tp2},
            "invalidations": ["환율 급등 지속", "미국 지수 급락 재개"],
            "desks": desks,
        },
        "historyModel": {
            "framework": "국내/해외 지수, 환율, 변동성 기반 역사 패턴 비교 엔진",
            "features": ["국내 지수 탄력", "미국 연동", "원달러", "변동성 레짐", "리스크온/오프 전환"],
            "currentInterpretation": "현재는 급변동 구간에서 회복 시도 국면으로, 추격보다 확인형 분할 진입이 합리적입니다.",
            "riskNote": "환율 재급등 + 미국 약세 동반 시 방어 모드로 즉시 전환 필요"
        },
        "kimchi": {"usdkrw": float(fx[-1]["Close"]), "btcKrw": float(ndq[-1]["Close"]), "coinKrw": float(current), "btcPrem": ndq_chg, "coinPrem": stock_chg},
        "indicators": indicators,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("updated", OUT)


if __name__ == "__main__":
    main()
