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

function renderCommittee(c) {
  const t = c.tradePlan;
  const fmt = (n) => Number(n).toLocaleString('ko-KR');
  document.getElementById('committeeTop').innerHTML = `
    <div class="card"><div>위원회 점수</div><h3>${c.score}/10</h3><span class="badge ${color(c.signal)}">${c.signal}</span></div>
    <div class="card"><div>최종 의견</div><h3>${c.decision}</h3></div>
    <div class="card"><div>종합 매매전략</div>
      <small>현재가: ${fmt(t.currentPrice)}원</small>
      <small>1차 매수: ${fmt(t.entry1.price)}원 (${t.entry1.allocation})</small>
      <small>2차 매수: ${fmt(t.entry2.price)}원 (${t.entry2.allocation})</small>
      <small>3차 매수: ${fmt(t.entry3.price)}원 (${t.entry3.allocation})</small>
      <small>손절: ${fmt(t.stopLoss)}원</small>
      <small>익절 1차: ${fmt(t.takeProfit1)}원 / 2차: ${fmt(t.takeProfit2)}원</small>
    </div>
  `;
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

function renderDesks(desks) {
  document.getElementById('desks').innerHTML = desks.map((d) => `
    <div class="desk-item">
      <div class="top"><b>${d.name}</b><span class="badge ${recClass(d.recommendation)}">${d.recommendation}</span></div>
      <small>점수: ${d.score}/10 (${d.signal})</small>
      <small>핵심 논리: ${d.thesis}</small>
      <small>행동 제안: ${d.action}</small>
    </div>
  `).join('');
}

function renderHistory(rows) {
  document.getElementById('history').innerHTML = rows.map((h) => `
    <div class="item">
      <div class="top"><b>${h.year} ${h.type} 국면</b><span class="badge ${h.return30d >= 0 ? 'g' : 'r'}">30D ${h.return30d}%</span></div>
      <small>${h.note}</small>
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
  const data = await loadData();
  document.getElementById('generatedAt').textContent = `업데이트: ${new Date(data.generatedAt).toLocaleString('ko-KR')}`;

  renderSummary(data.summary, data.targetCoin || 'ETH');
  renderCommittee(data.committee);
  renderKimchi(data.kimchi);
  renderDesks(data.committee.desks || []);
  renderHistory(data.historyComparisons || []);
  renderIndicators(data.indicators || []);
}

main().catch((e) => {
  document.getElementById('generatedAt').textContent = `오류: ${e.message}`;
});