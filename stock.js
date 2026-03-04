const color = (s) => (s === '청신호' ? 'g' : s === '관망' ? 'w' : 'r');
const recClass = (r) => {
  if (r === '공격 진입 가능') return 'rec-strong-buy';
  if (r === '분할 진입 구간') return 'rec-buy';
  if (r === '관망/대기') return 'rec-hold';
  if (r === '비중 축소 고려') return 'rec-sell';
  return 'rec-strong-sell';
};

async function loadData() {
  const r = await fetch('./data/stock_dashboard_data.json?v=' + Date.now());
  if (!r.ok) throw new Error('대시보드 데이터 로드 실패');
  return r.json();
}

function positionGuides(rec) {
  const map = {
    '공격 진입 가능': { holder: '보유자: 코어 유지 + 추세추종 가능', noPos: '무포지션: 1차 진입 가능' },
    '분할 진입 구간': { holder: '보유자: 계획 유지', noPos: '무포지션: 분할 진입 시작' },
    '관망/대기': { holder: '보유자: 과도한 액션 자제', noPos: '무포지션: 확인 후 진입' },
    '비중 축소 고려': { holder: '보유자: 반등 시 일부 축소', noPos: '무포지션: 신규 보류' },
    '방어 최우선': { holder: '보유자: 리스크 우선', noPos: '무포지션: 대기' }
  };
  return map[rec] || { holder: '보유자: 계획 유지', noPos: '무포지션: 대기' };
}

function renderSummary(s, t) {
  document.getElementById('summary').innerHTML = `
    <div class="card"><div>${t} 종합 신호지수</div><h3>${s.index100}/100</h3><span class="badge ${color(s.signal)}">${s.signal}</span></div>
    <div class="card"><div>긍정 신호 수</div><h3>${s.green}</h3></div>
    <div class="card"><div>경계 신호 수</div><h3>${s.red}</h3></div>`;
}

function renderCommittee(c, t) {
  const p = c.tradePlan; const fmt = (n)=>Number(n).toLocaleString('ko-KR');
  document.getElementById('committeeTop').innerHTML = `
    <div class="card"><div>위원회 점수</div><h3>${c.score}/10</h3><span class="badge ${color(c.signal)}">${c.signal}</span></div>
    <div class="card"><div>최종 의견</div><h3>${c.decision}</h3></div>
    <div class="card"><div>${t} 종합 매매전략</div>
      <small>현재가: ${fmt(p.currentPrice)}</small>
      <small>1차: ${fmt(p.entry1.price)} (${p.entry1.allocation})</small>
      <small>2차: ${fmt(p.entry2.price)} (${p.entry2.allocation})</small>
      <small>3차: ${fmt(p.entry3.price)} (${p.entry3.allocation})</small>
      <small>손절: ${fmt(p.stopLoss)} / 익절: ${fmt(p.takeProfit1)}, ${fmt(p.takeProfit2)}</small></div>`;
}

function renderMarket(k, t) {
  document.getElementById('kimchi').innerHTML = `
    <div class="card"><div>USD/KRW</div><h3>${Number(k.usdkrw).toFixed(2)}</h3></div>
    <div class="card"><div>NASDAQ 변동</div><h3>${Number(k.btcPrem).toFixed(2)}%</h3></div>
    <div class="card"><div>${t} 변동</div><h3>${Number(k.coinPrem).toFixed(2)}%</h3></div>`;
}

function renderDesks(desks) {
  document.getElementById('desks').innerHTML = desks.map(d => {
    const g=positionGuides(d.recommendation);
    return `<div class="desk-item ${recClass(d.recommendation)}"><div class="top"><b>${d.name}</b><span class="badge">${d.recommendation}</span></div><small>점수: ${d.score}/10 (${d.signal})</small><small>핵심 논리: ${d.thesis}</small><small>행동 제안: ${d.action}</small><small>📌 ${g.holder}</small><small>🧭 ${g.noPos}</small></div>`;
  }).join('');
}

function renderHistoryModel(h){document.getElementById('historyModel').innerHTML=`<div class="item"><div class="top"><b>패턴 엔진 상태</b><span class="badge g">활성</span></div><small>비교 프레임: ${h.framework}</small><small>반영된 기준: ${(h.features||[]).join(', ')}</small><small>현재 해석: ${h.currentInterpretation}</small><small>주의 포인트: ${h.riskNote}</small></div>`}
function renderIndicators(ind){document.getElementById('cryptoIndicators').innerHTML=(ind||[]).map(i=>`<div class="item"><div class="top"><b>${i.name}</b><span class="badge ${color(i.signal)}">${i.score}/10 · ${i.signal}</span></div><small>근거: ${i.reason}</small><small>코멘트: ${i.comment}</small></div>`).join('')}

async function main(){
  const d=await loadData();
  const t=d.targetCoin||'KOSPI';
  document.title=`${t} - 투자위원회 의견`;
  document.querySelector('.hero h1').textContent=`${t} - 투자위원회 의견`;
  document.getElementById('generatedAt').textContent=`업데이트: ${new Date(d.generatedAt).toLocaleString('ko-KR')}`;
  renderDesks(d.committee.desks||[]); renderCommittee(d.committee,t); renderMarket(d.kimchi,t); renderHistoryModel(d.historyModel||{}); renderIndicators(d.indicators||[]); renderSummary(d.summary,t);
}
main().catch(e=>document.getElementById('generatedAt').textContent='오류: '+e.message);