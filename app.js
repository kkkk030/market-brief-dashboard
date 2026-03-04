const sig = (s) => (s >= 6.5 ? '청신호' : s >= 3.5 ? '관망' : '적신호');
const color = (s) => (s === '청신호' ? 'g' : s === '관망' ? 'w' : 'r');
const clamp = (v, lo = 0, hi = 10) => Math.max(lo, Math.min(hi, v));

async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`API error: ${url}`);
  return r.json();
}

async function marketChart(coin) {
  return getJSON(`https://api.coingecko.com/api/v3/coins/${coin}/market_chart?vs_currency=usd&days=7&interval=hourly`);
}

function drawChart(canvasId, label, points, colorHex) {
  const ctx = document.getElementById(canvasId);
  const labels = points.map((p) => new Date(p[0]).toLocaleDateString('ko-KR', { month: 'numeric', day: 'numeric' }));
  const values = points.map((p) => p[1]);
  new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{ label, data: values, borderColor: colorHex, tension: 0.2, pointRadius: 0 }],
    },
    options: {
      responsive: true,
      plugins: { legend: { labels: { color: '#cbd5e1' } } },
      scales: {
        x: { ticks: { color: '#94a3b8', maxTicksLimit: 8 }, grid: { color: 'rgba(148,163,184,.15)' } },
        y: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148,163,184,.15)' } },
      },
    },
  });
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
    getJSON('https://api.coingecko.com/api/v3/coins/usd-coin/market_chart?vs_currency=usd&days=40&interval=daily'),
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

  const fB = Number(pB.lastFundingRate) * 100;
  const fE = Number(pE.lastFundingRate) * 100;
  const fAvg = (fB + fE) / 2;
  const oiChg = (Number(oi[1].sumOpenInterestValue) / Number(oi[0].sumOpenInterestValue) - 1) * 100;

  const ratio = Number(taker.at(-1).buySellRatio);
  const ratioPrev = Number(taker.at(-2).buySellRatio);
  const ratioChg = (ratio / ratioPrev - 1) * 100;

  const indicators = [];
  const add = (name, score, reason, comment) => indicators.push({ name, score: Number(score.toFixed(1)), signal: sig(score), reason, comment });

  add('유동성(스테이블 30D)', clamp(5 + stableBlend / 2), `USDT ${usdt30.toFixed(2)}%, USDC ${usdc30.toFixed(2)}%, 평균 ${stableBlend.toFixed(2)}%`, '스테이블 순증이면 대기자금 유입 여지가 있어 하방완충에 유리합니다.');
  add('BTC 도미넌스 구조', clamp(10 - Math.max(0, (btcDom - 52) * 0.6)), `BTC.D ${btcDom.toFixed(2)}%`, '도미넌스가 높을수록 알트 순환이 약해 ETH엔 불리합니다.');
  add('ETH/BTC 상대강도(7D)', clamp(5 + ethbtc7 / 1.2 - Math.max(0, (btcDom - 52) * 0.2)), `ETH/BTC 7D ${ethbtc7.toFixed(2)}%, 30D ${ethbtc30.toFixed(2)}%`, 'ETH가 BTC 대비 약하면 ETH 포지션은 보수적 관리가 필요합니다.');
  add('크립토 총시총 모멘텀(24H)', clamp(5 + totalMcap24h * 1.5), `Total MCap 24H ${totalMcap24h.toFixed(2)}%`, '시장 전체 체온 지표입니다. 음수 구간은 반등 신뢰도 낮음.');
  add('펀딩 과열도(BTC/ETH)', clamp(10 - Math.abs(fAvg - 0.005) * 120), `평균 펀딩 ${fAvg.toFixed(4)}%`, '펀딩 과열이 낮으면 급격한 롱청산 리스크가 상대적으로 낮습니다.');
  add('미결제약정 안정성(OI)', clamp(10 - Math.abs(oiChg) * 0.7), `BTC OI ${oiChg.toFixed(2)}%`, 'OI 급변은 변동성 확대 신호라 방어 규칙 유지가 유리합니다.');
  add('테이커 수급 균형', clamp(10 - Math.abs(ratio - 1.04) * 40 - Math.abs(ratioChg) * 0.2), `비율 ${ratio.toFixed(3)}, 전일 ${ratioChg.toFixed(2)}%`, '한쪽으로 과도하게 쏠리지 않은 수급은 분할 대응에 유리합니다.');
  add('시장 심리(Fear&Greed)', clamp(fear / 10), `F&G ${fear}/100`, '극단적 공포는 가짜 반등 빈도를 높이므로 확인매매가 유리합니다.');
  add('BTC 추세 모멘텀(7D)', clamp(5 + btc7d / 2), `BTC 7D ${btc7d.toFixed(2)}%`, 'BTC의 7일 추세는 시장 코어 리스크온/오프 판단에 중요합니다.');
  add('ETH 절대+상대 모멘텀', clamp(5 + eth7d / 2 + ethbtc7 / 4), `ETH 7D ${eth7d.toFixed(2)}%, 30D ${eth30d.toFixed(2)}%`, 'ETH 절대수익과 상대강도를 합쳐 실제 운용 난이도를 반영합니다.');

  return indicators;
}

function renderSummary(indicators) {
  const total = Number((indicators.reduce((a, b) => a + b.score, 0) / indicators.length).toFixed(1));
  const summary = [
    ['코인 10지표 종합', total, sig(total)],
    ['청신호 개수', indicators.filter((x) => x.signal === '청신호').length, '-'],
    ['적신호 개수', indicators.filter((x) => x.signal === '적신호').length, '-'],
  ];
  document.getElementById('summary').innerHTML = summary.map(([k, v, s]) => `
    <div class="card">
      <div>${k}</div>
      <h3>${v}</h3>
      ${s !== '-' ? `<span class="badge ${color(s)}">${s}</span>` : ''}
    </div>
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

async function main() {
  document.getElementById('generatedAt').textContent = `업데이트: ${new Date().toLocaleString('ko-KR')}`;

  const [btcChartData, ethChartData, indicators] = await Promise.all([
    marketChart('bitcoin'),
    marketChart('ethereum'),
    buildIndicators(),
  ]);

  drawChart('btcChart', 'BTC/USD', btcChartData.prices, '#f59e0b');
  drawChart('ethChart', 'ETH/USD', ethChartData.prices, '#60a5fa');
  renderSummary(indicators);
  renderIndicators(indicators);
}

main().catch((e) => {
  document.getElementById('generatedAt').textContent = `오류: ${e.message}`;
});