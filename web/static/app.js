/* ── Socket.IO connection ─────────────────────────────────────────────── */
const socket = io();

/* ── Chart setup ──────────────────────────────────────────────────────── */
const ctx = document.getElementById('price-chart').getContext('2d');
const priceChart = new Chart(ctx, {
  type: 'line',
  data: {
    labels: [],
    datasets: [
      {
        label: 'Price',
        data: [],
        borderColor: '#58a6ff',
        backgroundColor: 'rgba(88,166,255,0.08)',
        borderWidth: 2,
        pointRadius: 0,
        tension: 0.3,
        fill: true,
      },
      {
        label: 'SMA Short',
        data: [],
        borderColor: '#3fb950',
        borderWidth: 1.5,
        pointRadius: 0,
        borderDash: [4, 3],
        tension: 0.3,
        fill: false,
      },
      {
        label: 'SMA Long',
        data: [],
        borderColor: '#f85149',
        borderWidth: 1.5,
        pointRadius: 0,
        borderDash: [4, 3],
        tension: 0.3,
        fill: false,
      },
    ],
  },
  options: {
    responsive: true,
    animation: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: {
        labels: { color: '#8b949e', boxWidth: 14, font: { size: 11 } },
      },
      tooltip: {
        backgroundColor: '#161b22',
        borderColor: '#30363d',
        borderWidth: 1,
        titleColor: '#e6edf3',
        bodyColor: '#8b949e',
      },
    },
    scales: {
      x: {
        ticks: { color: '#8b949e', maxTicksLimit: 8, font: { size: 10 } },
        grid:  { color: '#21262d' },
      },
      y: {
        ticks: { color: '#8b949e', font: { size: 10 } },
        grid:  { color: '#21262d' },
      },
    },
  },
});

/* ── State update handler ─────────────────────────────────────────────── */
socket.on('state', (s) => applyState(s));
socket.on('log',   (d) => appendLog(d.line));
socket.on('logs',  (d) => d.lines.forEach(appendLog));

function applyState(s) {
  // Header badges
  const netBadge  = document.getElementById('network-badge');
  const modeBadge = document.getElementById('mode-badge');
  netBadge.textContent  = s.testnet ? 'Testnet' : 'Mainnet';
  netBadge.className    = 'badge ' + (s.testnet ? 'badge-testnet' : 'badge-mainnet');
  modeBadge.textContent = s.dry_run ? 'Dry Run' : 'Live';
  modeBadge.className   = 'badge ' + (s.dry_run ? 'badge-dry' : 'badge-live');

  // Status
  const dot   = document.getElementById('status-dot');
  const label = document.getElementById('status-label');
  if (s.error) {
    dot.className = 'status-dot error';
    label.textContent = 'Error';
    showError(s.error);
  } else if (s.running) {
    dot.className = 'status-dot running';
    label.textContent = 'Running';
    hideError();
  } else {
    dot.className = 'status-dot stopped';
    label.textContent = 'Stopped';
  }

  // Buttons
  document.getElementById('btn-start').disabled = s.running;
  document.getElementById('btn-stop').disabled  = !s.running;
  setConfigDisabled(s.running);

  // Stats
  setText('stat-eth',      s.eth_balance   != null ? s.eth_balance.toFixed(6) + ' ETH' : '—');
  setText('stat-token',    s.token_balance != null ? s.token_balance.toFixed(4) + ' ' + s.token : '—');
  setText('stat-price',    s.current_price != null ? '$' + s.current_price.toFixed(4) : '—');
  setText('stat-entry',    s.entry_price   != null ? '$' + s.entry_price.toFixed(4) : '—');
  setText('stat-position', s.position_eth  != null ? s.position_eth.toFixed(6) + ' ETH' : '—');
  setText('stat-trades',   s.trade_count ?? 0);
  setText('stat-sma-short', s.sma_short != null ? s.sma_short.toFixed(4) : '—');
  setText('stat-sma-long',  s.sma_long  != null ? s.sma_long.toFixed(4)  : '—');
  setText('stat-rsi',       s.rsi       != null ? s.rsi.toFixed(1)       : '—');
  document.getElementById('stat-token-label').textContent = s.token + ' Balance';
  document.getElementById('chart-pair').textContent = 'WETH / ' + s.token;

  // PnL with colour
  const pnlEl = document.getElementById('stat-pnl');
  if (s.pnl_pct != null) {
    const sign = s.pnl_pct >= 0 ? '+' : '';
    pnlEl.textContent = sign + s.pnl_pct.toFixed(2) + '%';
    pnlEl.style.color = s.pnl_pct >= 0 ? 'var(--green)' : 'var(--red)';
  } else {
    pnlEl.textContent = '—';
    pnlEl.style.color = '';
  }

  // Signal
  const sig = (s.last_signal || 'HOLD').toLowerCase();
  const sigBox = document.getElementById('signal-box');
  sigBox.textContent = s.last_signal || 'HOLD';
  sigBox.className   = 'signal-box ' + sig;
  document.getElementById('confidence-bar').style.width =
    ((s.last_signal_confidence || 0) * 100).toFixed(1) + '%';
  document.getElementById('signal-reason').textContent =
    s.last_signal_reason || 'Waiting for data…';

  // Price chart
  if (s.price_history && s.price_history.length > 0) {
    const labels = s.price_history.map(p => p.t.slice(11, 19));
    const prices = s.price_history.map(p => p.price);
    priceChart.data.labels = labels;
    priceChart.data.datasets[0].data = prices;

    // SMA lines (flat fill to match length)
    if (s.sma_short != null) {
      priceChart.data.datasets[1].data = Array(prices.length).fill(null);
      priceChart.data.datasets[1].data[prices.length - 1] = s.sma_short;
    }
    if (s.sma_long != null) {
      priceChart.data.datasets[2].data = Array(prices.length).fill(null);
      priceChart.data.datasets[2].data[prices.length - 1] = s.sma_long;
    }
    priceChart.update('none');
  }

  // Trade log
  renderTradeLog(s.trade_log || []);
}

/* ── Trade log ────────────────────────────────────────────────────────── */
function renderTradeLog(trades) {
  const tbody = document.getElementById('trade-tbody');
  const noTrades = document.getElementById('no-trades');
  if (!trades.length) {
    tbody.innerHTML = '';
    noTrades.classList.remove('hidden');
    return;
  }
  noTrades.classList.add('hidden');
  tbody.innerHTML = [...trades].reverse().map(t => {
    const cls = t.action.startsWith('BUY') ? 'buy' : 'sell';
    return `<tr>
      <td>${t.time}</td>
      <td class="${cls}">${t.action}</td>
      <td>$${t.price}</td>
      <td>${t.amount}</td>
    </tr>`;
  }).join('');
}

/* ── Log console ──────────────────────────────────────────────────────── */
function appendLog(line) {
  const console_ = document.getElementById('log-console');
  const div = document.createElement('div');
  div.className = 'log-line ' + logClass(line);
  div.textContent = line;
  console_.appendChild(div);
  // Keep max 300 lines
  while (console_.children.length > 300) console_.removeChild(console_.firstChild);
  console_.scrollTop = console_.scrollHeight;
}

function logClass(line) {
  if (line.includes('[WARNING]') || line.includes('[WARN]')) return 'warn';
  if (line.includes('[ERROR]') || line.includes('[CRITICAL]')) return 'error';
  return 'info';
}

function clearLog() {
  document.getElementById('log-console').innerHTML = '';
}

/* ── Agent controls ───────────────────────────────────────────────────── */
async function startAgent() {
  hideError();
  const payload = {
    testnet:          document.getElementById('cfg-network').value === 'testnet',
    dry_run:          document.getElementById('cfg-mode').value === 'dry',
    token:            document.getElementById('cfg-token').value,
    strategy:         document.getElementById('cfg-strategy').value,
    trade_amount_eth: parseFloat(document.getElementById('cfg-amount').value),
    polling_interval: parseInt(document.getElementById('cfg-interval').value),
    max_slippage:     parseFloat(document.getElementById('cfg-slippage').value),
  };
  try {
    const res = await fetch('/api/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) showError(data.error || 'Failed to start agent');
  } catch (e) {
    showError('Network error: ' + e.message);
  }
}

async function stopAgent() {
  try {
    await fetch('/api/stop', { method: 'POST' });
  } catch (e) {
    showError('Network error: ' + e.message);
  }
}

/* ── Helpers ──────────────────────────────────────────────────────────── */
function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

function showError(msg) {
  const el = document.getElementById('error-msg');
  el.textContent = msg;
  el.classList.remove('hidden');
}

function hideError() {
  document.getElementById('error-msg').classList.add('hidden');
}

function setConfigDisabled(disabled) {
  ['cfg-network','cfg-mode','cfg-token','cfg-strategy',
   'cfg-amount','cfg-interval','cfg-slippage'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.disabled = disabled;
  });
}

/* ── Initial state fetch (in case socket is slow) ─────────────────────── */
fetch('/api/state').then(r => r.json()).then(applyState).catch(() => {});
