async function run() {
  const res = await fetch('./data/latest_unified_report.json');
  const data = await res.json();

  document.getElementById('generatedAt').textContent = `생성 시각: ${data.generatedAt}`;

  const s = data.summary;
  const summary = [
    ['주식 점수', s.stockScore, s.stockSignal],
    ['코인 점수', s.cryptoScore, s.cryptoSignal],
    ['통합 점수', s.totalScore, s.totalSignal],
  ];

  const color = (sig) => sig === '청신호' ? 'g' : sig === '관망' ? 'w' : 'r';

  document.getElementById('summary').innerHTML = summary.map(([k,v,sig]) =>
    `<div class="card"><div>${k}</div><h3>${v ?? '-'} / 10</h3><span class="badge ${color(sig)}">${sig ?? '-'}</span></div>`
  ).join('');

  document.getElementById('stockIndicators').innerHTML = data.stocks.indicators.map(i =>
    `<div class="item"><b>${i.name}</b> — ${i.score}/10<br/><small>${i.comment}</small></div>`
  ).join('');

  const crypto = data.crypto?.indicators ?? [];
  document.getElementById('cryptoIndicators').innerHTML = crypto.map(i =>
    `<div class="item"><b>${i.name}</b> — ${i.score}/10 (${i.signal})<br/><small>${i.reason}</small><br/><small>${i.comment}</small></div>`
  ).join('');

  const news = [
    ...(data.overnight?.stock_news ?? []),
    ...(data.overnight?.crypto_news ?? [])
  ].slice(0,8);

  document.getElementById('news').innerHTML = news.map(n => `<li><a href="${n.link}" target="_blank">${n.title}</a></li>`).join('');
}
run();