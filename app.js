const color = (s) => (s === '청신호' ? 'g' : s === '관망' ? 'w' : 'r');

const recClass = (r) => {
  if (r === '매수적극추천') return 'rec-strong-buy';
  if (r === '매수추천') return 'rec-buy';
  if (r === '관망') return 'rec-hold';
  if (r === '매도추천') return 'rec-sell';
  return 'rec-strong-sell';
};

async function loadData() {
  const r = await fetch('./data/dashboard_data.json?v=' + Date.now());
  if (!r.ok) throw new Error('대시보드 데이터 로드 실패');
  return r.json();
}

function renderSummary(s, coin) {
  document.getElementById('summary').innerHTML = `
    <div class="card"><div>${coin} 10지표 종합</div><h3>${s.total}/10</h3><span class="badge ${color(s.signal)}">${s.signal}</span></div>
    <div class="card"><div>청신호</div><h3>${s.green}</h3></div>
    <div class="card"><div>적신호</div><h3>${s.red}</h3></div>
  `;
}

function renderCommittee(c, coin) {
  const t = c.tradePlan;
  const fmt = (n) => Number(n).toLocaleString('ko-KR');
  document.getElementById('committeeTop').innerHTML = `
    <div class="card"><div>위원회 점수</div><h3>${c.score}/10</h3><span class="badge ${color(c.signal)}">${c.signal}</span></div>
    <div class="card"><div>최종 의견</div><h3>${c.decision}</h3></div>
    <div class="card"><div>${coin} 종합 매매전략</div>
      <small>현재가: ${fmt(t.currentPrice)}원</small>
      <small>1차 매수: ${fmt(t.entry1.price)}원 (${t.entry1.allocation})</small>
      <small>2차 매수: ${fmt(t.entry2.price)}원 (${t.entry2.allocation})</small>
      <small>3차 매수: ${fmt(t.entry3.price)}원 (${t.entry3.allocation})</small>
      <small>손절: ${fmt(t.stopLoss)}원</small>
      <small>익절 1차: ${fmt(t.takeProfit1)}원 / 2차: ${fmt(t.takeProfit2)}원</small>
    </div>
  `;
}

function renderKimchi(k, coin) {
  const fmt = (n) => Number(n ?? 0).toLocaleString('ko-KR', { maximumFractionDigits: 0 });
  const chip = (v) => {
    const n = Number(v ?? 0);
    return n >= 0 ? `+${n.toFixed(2)}%` : `${n.toFixed(2)}%`;
  };

  const coinKrw = k.coinKrw ?? k.ethKrw;
  const coinPrem = k.coinPrem ?? k.ethPrem;
  const usdkrw = Number(k.usdkrw ?? 0);
  const btcPrem = Number(k.btcPrem ?? 0);

  document.getElementById('kimchi').innerHTML = `
    <div class="card"><div>USD/KRW</div><h3>${usdkrw.toFixed(2)}</h3></div>
    <div class="card"><div>BTC 업비트</div><h3>${fmt(k.btcKrw)}원</h3><span class="badge ${btcPrem >= 0 ? 'w' : 'g'}">김프 ${chip(btcPrem)}</span></div>
    <div class="card"><div>${coin} 업비트</div><h3>${fmt(coinKrw)}원</h3><span class="badge ${Number(coinPrem ?? 0) >= 0 ? 'w' : 'g'}">김프 ${chip(coinPrem)}</span></div>
  `;
}

function friendlyDeskName(name) {
  const m = {
    'Regime Desk': '시장 분위기 팀',
    'Macro Liquidity Desk': '유동성/거시 팀',
    'On-chain/Flow Desk': '자금흐름 팀',
    'Derivatives Desk': '파생 포지션 팀',
    'Technical Structure Desk': '차트/추세 팀',
    'Relative Value Desk': '상대강도 팀',
    'Event/Narrative Desk': '뉴스/이슈 팀',
    'Risk Control Desk': '리스크 관리 팀'
  };
  return m[name] || name;
}

function renderDesks(desks) {
  document.getElementById('desks').innerHTML = desks.map((d) => `
    <div class="desk-item ${recClass(d.recommendation)}">
      <div class="top"><b>${friendlyDeskName(d.name)}</b><span class="badge">${d.recommendation}</span></div>
      <small>점수: ${d.score}/10 (${d.signal})</small>
      <small>핵심 논리: ${d.thesis}</small>
      <small>행동 제안: ${d.action}</small>
    </div>
  `).join('');
}

function renderHistoryModel(h) {
  document.getElementById('historyModel').innerHTML = `
    <div class="item">
      <div class="top"><b>패턴 엔진 상태</b><span class="badge g">활성</span></div>
      <small>비교 프레임: ${h.framework}</small>
      <small>반영된 기준: ${h.features.join(', ')}</small>
      <small>현재 해석: ${h.currentInterpretation}</small>
      <small>주의 포인트: ${h.riskNote}</small>
    </div>
  `;
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
  const data = await loadData();
  document.getElementById('generatedAt').textContent = `업데이트: ${new Date(data.generatedAt).toLocaleString('ko-KR')}`;

  const coin = data.targetCoin || 'ETH';
  document.title = `${coin} - 투자위원회 의견`;
  const titleEl = document.querySelector('.hero h1');
  if (titleEl) titleEl.textContent = `${coin} - 투자위원회 의견`;
  renderSummary(data.summary, coin);
  renderCommittee(data.committee, coin);
  renderKimchi(data.kimchi, coin);
  renderDesks(data.committee.desks || []);
  renderHistoryModel(data.historyModel || {framework:'N/A',features:[],currentInterpretation:'N/A',riskNote:'N/A'});
  renderIndicators(data.indicators || []);
}

main().catch((e) => {
  document.getElementById('generatedAt').textContent = `오류: ${e.message}`;
});