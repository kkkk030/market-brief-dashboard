const sig = (s) => (s >= 6.5 ? '청신호' : s >= 3.5 ? '관망' : '적신호');
const color = (s) => (s === '청신호' ? 'g' : s === '관망' ? 'w' : 'r');
const clamp = (v, lo = 0, hi = 10) => Math.max(lo, Math.min(hi, v));

async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${url}`);
  return r.json();
}

function drawChart(canvasId, label, points, colorHex) {
  const ctx = document.getElementById(canvasId);
  if (!ctx || !points?.length) return;
  const labels = points.map((p) => new Date(p[0]).toLocaleDateString('ko-KR', { month: 'numeric', day: 'numeric' }));
  const values = points.map((p) => p[1]);
  new Chart(ctx, {
    type: 'line',
    data: { labels, datasets: [{ label, data: values, borderColor: colorHex, tension: 0.2, pointRadius: 0 }] },
    options: {
      responsive: true,
      plugins: { legend: { labels: { color: '#cbd5e1' } } },
      scales: {
        x: { ticks: { color: '#94a3b8', maxTicksLimit: 8 }, grid: { color: 'rgba(148,163,184,.15)' } },
        y: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148,163,184,.15)' } }
      }
    }
  });
}

async function getKimchiPremium() {
  const [upbitBtc, upbitEth, cg, fx] = await Promise.all([
    getJSON('https://api.upbit.com/v1/ticker?markets=KRW-BTC'),
    getJSON('https://api.upbit.com/v1/ticker?markets=KRW-ETH'),
    getJSON('https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd'),
    getJSON('https://open.er-api.com/v6/latest/USD')
  ]);

  const usdkrw = fx.rates.KRW;
  const btcKrw = upbitBtc[0].trade_price;
  const ethKrw = upbitEth[0].trade_price;
  const btcFair = cg.bitcoin.usd * usdkrw;
  const ethFair = cg.ethereum.usd * usdkrw;
  const btcPrem = (btcKrw / btcFair - 1) * 100;
  const ethPrem = (ethKrw / ethFair - 1) * 100;

  return { usdkrw, btcKrw, ethKrw, btcPrem, ethPrem };
}

async function buildIndicators() {
  const [global, fng, btc, eth, ethbtcKlines, pB, pE, oi, taker, usdt, usdc] = await Promise.all([
    getJSON('https://api.coingecko.com/api/v3/global'),
    getJSON('https://api.alternative.me/fng/?limit=1'),
    getJSON('https://api.coingecko.com/api/v3/coins/bitcoin?localization=false&tickers=false&market_data=true&community_data=false&developer_data=false&sparkline=false'),
    getJSON('https://api.coingecko.com/api/v3/coins/ethereum?localization=false&tickers=false&market_data=true&community_data=false&developer_data=false&sparkline=false'),
    getJSON('https://api.binance.com/api/v3/klines?symbol=ETHBTC&interval=1d&limit=31'),
    getJSON('https://fapi.binance.com/fapi/v1/premiumIndex?symbol=BTCUSDT'),
    getJSON('https://fapi.binance.com/fapi/v1/premiumIndex?symbol=ETHUSDT'),
    getJSON('https://fapi.binance.com/futures/data/openInterestHist?symbol=BTCUSDT&period=1d&limit=2'),
    getJSON('https://fapi.binance.com/futures/data/takerlongshortRatio?symbol=BTCUSDT&period=1d&limit=2'),
    getJSON('https://api.coingecko.com/api/v3/coins/tether/market_chart?vs_currency=usd&days=40&interval=daily'),
    getJSON('https://api.coingecko.com/api/v3/coins/usd-coin/market_chart?vs_currency=usd&days=40&interval=daily')
  ]);

  const btcDom = Number(global.data.market_cap_percentage.btc);
  const totalMcap24h = Number(global.data.market_cap_change_percentage_24h_usd);
  const fear = Number(fng.data[0].value);
  const usdtCaps = usdt.market_caps.map((x) => x[1]);
  const usdcCaps = usdc.market_caps.map((x) => x[1]);
  const usdt30 = (usdtCaps.at(-1) / usdtCaps.at(-31) - 1) * 100;
  const usdc30 = (usdcCaps.at(-1) / usdcCaps.at(-31) - 1) * 100;
  const stableBlend = (usdt30 + usdc30) / 2;

  const btc7d = Number(btc.market_data.price_change_percentage_7d);
  const eth7d = Number(eth.market_data.price_change_percentage_7d);
  const eth30d = Number(eth.market_data.price_change_percentage_30d);
  const closes = ethbtcKlines.map((k) => Number(k[4]));
  const ethbtc7 = (closes.at(-1) / closes.at(-8) - 1) * 100;
  const ethbtc30 = (closes.at(-1) / closes[0] - 1) * 100;
  const fAvg = (Number(pB.lastFundingRate) * 100 + Number(pE.lastFundingRate) * 100) / 2;
  const oiChg = (Number(oi[1].sumOpenInterestValue) / Number(oi[0].sumOpenInterestValue) - 1) * 100;
  const ratio = Number(taker.at(-1).buySellRatio);
  const ratioPrev = Number(taker.at(-2).buySellRatio);
  const ratioChg = (ratio / ratioPrev - 1) * 100;

  const list = [];
  const add = (name, score, reason, comment) => list.push({ name, score: Number(score.toFixed(1)), signal: sig(score), reason, comment });

  add('유동성(스테이블 30D)', clamp(5 + stableBlend / 2), `USDT ${usdt30.toFixed(2)}%, USDC ${usdc30.toFixed(2)}%`, '대기자금 유입 여력 체크 지표');
  add('BTC 도미넌스 구조', clamp(10 - Math.max(0, (btcDom - 52) * 0.6)), `BTC.D ${btcDom.toFixed(2)}%`, '높을수록 알트 순환 약함');
  add('ETH/BTC 상대강도(7D)', clamp(5 + ethbtc7 / 1.2 - Math.max(0, (btcDom - 52) * 0.2)), `ETH/BTC 7D ${ethbtc7.toFixed(2)}%, 30D ${ethbtc30.toFixed(2)}%`, 'ETH 상대강도 체크 핵심');
  add('크립토 총시총 모멘텀(24H)', clamp(5 + totalMcap24h * 1.5), `Total MCap 24H ${totalMcap24h.toFixed(2)}%`, '시장 체온 지표');
  add('펀딩 과열도(BTC/ETH)', clamp(10 - Math.abs(fAvg - 0.005) * 120), `평균 펀딩 ${fAvg.toFixed(4)}%`, '과열/청산 리스크 체크');
  add('미결제약정 안정성(OI)', clamp(10 - Math.abs(oiChg) * 0.7), `OI ${oiChg.toFixed(2)}%`, '레버리지 압력 체크');
  add('테이커 수급 균형', clamp(10 - Math.abs(ratio - 1.04) * 40 - Math.abs(ratioChg) * 0.2), `비율 ${ratio.toFixed(3)}, 전일 ${ratioChg.toFixed(2)}%`, '매수/매도 쏠림 체크');
  add('시장 심리(F&G)', clamp(fear / 10), `F&G ${fear}/100`, '극단 심리 구간 점검');
  add('BTC 추세 모멘텀(7D)', clamp(5 + btc7d / 2), `BTC 7D ${btc7d.toFixed(2)}%`, '코어 추세 확인');
  add('ETH 절대+상대 모멘텀', clamp(5 + eth7d / 2 + ethbtc7 / 4), `ETH 7D ${eth7d.toFixed(2)}%, 30D ${eth30d.toFixed(2)}%`, 'ETH 운용 난이도 반영');

  return list;
}

function renderSummary(indicators) {
  const total = Number((indicators.reduce((a, b) => a + b.score, 0) / indicators.length).toFixed(1));
  const cards = [
    ['코인 10지표 종합', `${total}/10`, sig(total)],
    ['청신호', indicators.filter((x) => x.signal === '청신호').length, '-'],
    ['적신호', indicators.filter((x) => x.signal === '적신호').length, '-']
  ];
  document.getElementById('summary').innerHTML = cards.map(([k, v, s]) => `
    <div class="card"><div>${k}</div><h3>${v}</h3>${s !== '-' ? `<span class="badge ${color(s)}">${s}</span>` : ''}</div>
  `).join('');
}

function renderIndicators(indicators) {
  document.getElementById('cryptoIndicators').innerHTML = indicators.map((i) => `
    <div class="item">
      <div class="top"><b>${i.name}</b><span class="badge ${color(i.signal)}">${i.score}/10 · ${i.signal}</span></div>
      <small>근거: ${i.reason}</small>
      <small>코멘트: ${i.comment}</small>
    </div>
  `).join('');
}

function renderKimchi(k) {
  const fmt = (n) => Number(n).toLocaleString('ko-KR', { maximumFractionDigits: 0 });
  const chip = (v) => (v >= 0 ? `+${v.toFixed(2)}%` : `${v.toFixed(2)}%`);
  document.getElementById('kimchi').innerHTML = `
    <div class="card"><div>USD/KRW</div><h3>${k.usdkrw.toFixed(2)}</h3></div>
    <div class="card"><div>BTC 업비트</div><h3>${fmt(k.btcKrw)}원</h3><span class="badge ${k.btcPrem >= 0 ? 'w' : 'g'}">김프 ${chip(k.btcPrem)}</span></div>
    <div class="card"><div>ETH 업비트</div><h3>${fmt(k.ethKrw)}원</h3><span class="badge ${k.ethPrem >= 0 ? 'w' : 'g'}">김프 ${chip(k.ethPrem)}</span></div>
  `;
}

async function main() {
  document.getElementById('generatedAt').textContent = `업데이트: ${new Date().toLocaleString('ko-KR')}`;

  const btcChartData = await getJSON('https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days=7&interval=hourly').catch(() => null);
  const ethChartData = await getJSON('https://api.coingecko.com/api/v3/coins/ethereum/market_chart?vs_currency=usd&days=7&interval=hourly').catch(() => null);
  const indicators = await buildIndicators().catch(() => []);
  const kimchi = await getKimchiPremium().catch(() => null);

  if (btcChartData) drawChart('btcChart', 'BTC/USD', btcChartData.prices, '#f59e0b');
  if (ethChartData) drawChart('ethChart', 'ETH/USD', ethChartData.prices, '#60a5fa');

  if (indicators.length) {
    renderSummary(indicators);
    renderIndicators(indicators);
  } else {
    document.getElementById('cryptoIndicators').innerHTML = '<div class="item">지표 로드 실패. 잠시 후 새로고침해주세요.</div>';
  }

  if (kimchi) renderKimchi(kimchi);
  else document.getElementById('kimchi').innerHTML = '<div class="card">김치 프리미엄 로드 실패</div>';
}

main();