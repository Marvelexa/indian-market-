/**
 * NEXUS BHARAT - Main Terminal Application Controller
 * Handles 2+2+2 Seat Architecture, Institutional Sniper Scanner, Live Feeds, Level-2 Depth & Audio Feedback
 */

class NexusTerminalApp {
  constructor() {
    this.selectedSymbol = '^NSEI';
    this.selectedTimeframe = '1D';
    this.activeFilter = 'all';

    this.quotes = {};
    this.overviewData = null;
    this.portfolioData = null;
    this.sniperSignals = [];
    this.seatsData = [];
    this.sessionData = null;

    // Order Ticket State
    this.orderSide = 'BUY';
    this.orderProduct = 'MIS'; // 'MIS' (5x) or 'CNC' (1x)
    this.orderType = 'MARKET'; // 'MARKET', 'LIMIT', 'SL'
    this.orderQty = 25;        // Default 1 lot of Nifty 50
    this.orderPrice = 25144.30;
    this.orderSlPrice = null;
    this.orderTpPrice = null;

    this.chartManager = null;
    this.audioCtx = null;
    this.currentView = 'terminal';

    // Time Machine Replay State
    this.isTimeMachineOpen = false;
    this.replayPollingTimer = null;
    this.replayState = null;

    this.initAudio();
    this.initElements();
    this.initEvents();
    this.initShortcuts();

    // Start App
    this.startBootstrap();
  }

  initAudio() {
    try {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (AudioContext) {
        this.audioCtx = new AudioContext();
      }
    } catch (e) {
      console.warn("Audio context not supported");
    }
  }

  playBeep(freq = 800, type = 'sine', duration = 0.05) {
    if (!this.audioCtx) return;
    try {
      if (this.audioCtx.state === 'suspended') {
        this.audioCtx.resume();
      }
      const osc = this.audioCtx.createOscillator();
      const gain = this.audioCtx.createGain();
      osc.type = type;
      osc.frequency.setValueAtTime(freq, this.audioCtx.currentTime);
      gain.gain.setValueAtTime(0.08, this.audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, this.audioCtx.currentTime + duration);
      osc.connect(gain);
      gain.connect(this.audioCtx.destination);
      osc.start();
      osc.stop(this.audioCtx.currentTime + duration);
    } catch (e) {}
  }

  playOrderSound(isSuccess = true) {
    if (isSuccess) {
      this.playBeep(587.33, 'triangle', 0.06); // D5
      setTimeout(() => this.playBeep(880.00, 'triangle', 0.08), 70); // A5
    } else {
      this.playBeep(220, 'sawtooth', 0.12);
    }
  }

  initElements() {
    this.chartManager = new NexusChartManager('tv-chart-main', 'tv-chart-rsi');
  }

  initEvents() {
    // Search input
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
      searchInput.addEventListener('input', (e) => {
        this.filterWatchlist(e.target.value);
      });
    }

    // Timeframe selector
    document.querySelectorAll('.tf-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        document.querySelectorAll('.tf-btn').forEach(b => b.classList.remove('active'));
        e.currentTarget.classList.add('active');
        this.selectedTimeframe = e.currentTarget.dataset.tf;
        this.playBeep(440, 'sine', 0.03);
        this.loadChart();
      });
    });

    // Indicator toggles
    document.querySelectorAll('.indicator-toggle').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const ind = e.currentTarget.dataset.ind;
        const isActive = this.chartManager.toggleIndicator(ind);
        e.currentTarget.classList.toggle('active', isActive);
        this.playBeep(600, 'sine', 0.02);
      });
    });

    // Watchlist sector filters
    document.querySelectorAll('.w-tab').forEach(tab => {
      tab.addEventListener('click', (e) => {
        document.querySelectorAll('.w-tab').forEach(t => t.classList.remove('active'));
        e.currentTarget.classList.add('active');
        this.activeFilter = e.currentTarget.dataset.filter;
        this.playBeep(520, 'sine', 0.02);
        this.renderWatchlist();
      });
    });

    // Top Navigation Tabs
    document.querySelectorAll('.nav-tab').forEach(tab => {
      tab.addEventListener('click', (e) => {
        const view = e.currentTarget.id.replace('nav-btn-', '');
        this.switchView(view);
      });
    });

    // Drawer tabs
    document.querySelectorAll('.d-tab').forEach(tab => {
      tab.addEventListener('click', (e) => {
        if (e.currentTarget.id === 'tab-launch-time-machine') {
          this.openTimeMachineFullPage();
          return;
        }
        document.querySelectorAll('.d-tab').forEach(t => t.classList.remove('active'));
        e.currentTarget.classList.add('active');
        const tabId = e.currentTarget.dataset.drawer;
        this.switchDrawerTab(tabId);
        this.playBeep(480, 'sine', 0.02);
      });
    });

    // Time-Machine Full-Page Launch Buttons
    const btnOpenTM = document.getElementById('btn-open-time-machine');
    if (btnOpenTM) {
      btnOpenTM.addEventListener('click', () => this.openTimeMachineFullPage());
    }
    const btnTopTM = document.getElementById('btn-top-time-machine');
    if (btnTopTM) {
      btnTopTM.addEventListener('click', () => this.openTimeMachineFullPage());
    }

    // Time-Machine Exit Button
    const btnExitTM = document.getElementById('tm-btn-exit');
    if (btnExitTM) {
      btnExitTM.addEventListener('click', () => this.exitTimeMachineFullPage());
    }

    // Time-Machine Play / Pause / Reset Controls
    const btnPlayTM = document.getElementById('tm-btn-play');
    if (btnPlayTM) {
      btnPlayTM.addEventListener('click', () => {
        // If market is closed (22,500s), automatically restart the day from 09:15:00 AM IST!
        if (this.replayState && (this.replayState.secondOfDay >= 22500 || this.replayState.sessionGate === 'MARKET_CLOSED')) {
          const select = document.getElementById('tm-date-select');
          const d = (select && select.value) || (this.replayState && this.replayState.currentDate) || '2026-11-13';
          this.applySelectedDate(d);
        } else {
          this.sendReplayControl('PLAY');
        }
      });
    }
    const btnPauseTM = document.getElementById('tm-btn-pause');
    if (btnPauseTM) {
      btnPauseTM.addEventListener('click', () => this.sendReplayControl('PAUSE'));
    }
    const btnResetTM = document.getElementById('tm-btn-reset');
    if (btnResetTM) {
      btnResetTM.addEventListener('click', () => {
        const select = document.getElementById('tm-date-select');
        const d = (select && select.value) || (this.replayState && this.replayState.currentDate) || '2026-11-13';
        this.applySelectedDate(d);
      });
    }

    // Date Selector & Load Button
    const btnLoadDate = document.getElementById('tm-btn-load-date');
    if (btnLoadDate) {
      btnLoadDate.addEventListener('click', () => {
        const select = document.getElementById('tm-date-select');
        const d = select ? select.value : '2026-11-13';
        this.applySelectedDate(d);
      });
    }
    const dateSelect = document.getElementById('tm-date-select');
    if (dateSelect) {
      dateSelect.addEventListener('change', (e) => {
        const targetD = e.target.value;
        if (targetD) this.applySelectedDate(targetD);
      });
    }

    // Quick Date Preset Chips
    document.querySelectorAll('.tm-date-chip').forEach(chip => {
      chip.addEventListener('click', (e) => {
        const d = e.currentTarget.dataset.date;
        if (d) this.applySelectedDate(d);
      });
    });

    // Speed Selector Buttons (1x, 5x, 10x, 30x, 60x, 150x, 300x, 600x Turbo)
    document.querySelectorAll('.tm-speed-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const speed = parseInt(e.currentTarget.dataset.speed);
        this.sendReplayControl('SET_SPEED', { speed });
        this.playBeep(580, 'sine', 0.02);
      });
    });

    // Milestone Jump Buttons
    document.querySelectorAll('.tm-jump-sec').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const sec = parseInt(e.currentTarget.dataset.sec);
        this.sendReplayControl('SET_SECOND', { secondOfDay: sec });
        this.playBeep(520, 'sine', 0.03);
      });
    });

    // Intraday Timeline Scrubber Slider (0 to 22,500s)
    const secondSlider = document.getElementById('tm-second-slider');
    if (secondSlider) {
      secondSlider.addEventListener('input', (e) => {
        const sec = parseInt(e.target.value);
        this.sendReplayControl('SET_SECOND', { secondOfDay: sec });
      });
    }

    // 60D Historical Open Button in Header
    const btnOpenHist = document.getElementById('btn-open-historical');
    if (btnOpenHist) {
      btnOpenHist.addEventListener('click', () => {
        const histTab = document.getElementById('tab-historical');
        if (histTab) {
          histTab.click();
          histTab.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
      });
    }

    // Historical Plot 60D on Chart Button
    const btnHistPlot = document.getElementById('btn-hist-load-chart');
    if (btnHistPlot) {
      btnHistPlot.addEventListener('click', () => {
        document.querySelectorAll('.tf-btn').forEach(b => {
          b.classList.toggle('active', b.dataset.tf === '60D');
        });
        this.selectedTimeframe = '60D';
        this.loadChart();
      });
    }

    // Side Toggle (BUY / SELL)
    const btnBuy = document.getElementById('side-buy');
    const btnSell = document.getElementById('side-sell');
    if (btnBuy && btnSell) {
      btnBuy.addEventListener('click', () => this.setSide('BUY'));
      btnSell.addEventListener('click', () => this.setSide('SELL'));
    }

    // Product Toggle (MIS / CNC)
    document.querySelectorAll('.prod-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        document.querySelectorAll('.prod-btn').forEach(b => b.classList.remove('active'));
        e.currentTarget.classList.add('active');
        this.orderProduct = e.currentTarget.dataset.prod;
        this.updateMarginSummary();
        this.playBeep(500, 'sine', 0.02);
      });
    });

    // Order Type Selector
    const typeSelect = document.getElementById('order-type-select');
    if (typeSelect) {
      typeSelect.addEventListener('change', (e) => {
        this.orderType = e.target.value;
        const priceInput = document.getElementById('order-price-input');
        if (this.orderType === 'MARKET') {
          priceInput.disabled = true;
          const q = this.quotes[this.selectedSymbol];
          if (q) priceInput.value = q.ltp;
        } else {
          priceInput.disabled = false;
        }
        this.updateMarginSummary();
      });
    }

    // Quantity Input & Quick Qty Pills
    const qtyInput = document.getElementById('order-qty-input');
    if (qtyInput) {
      qtyInput.addEventListener('input', (e) => {
        this.orderQty = Math.max(1, parseInt(e.target.value) || 1);
        this.updateMarginSummary();
      });
    }

    document.querySelectorAll('.qty-pill').forEach(pill => {
      pill.addEventListener('click', (e) => {
        const mult = parseInt(e.currentTarget.dataset.lot);
        const q = this.quotes[this.selectedSymbol];
        const lotSize = (q && q.lot_size) ? q.lot_size : 25;
        this.orderQty = mult * lotSize;
        if (qtyInput) qtyInput.value = this.orderQty;
        this.updateMarginSummary();
        this.playBeep(700, 'sine', 0.02);
      });
    });

    // Steppers
    const qtyMinus = document.getElementById('qty-minus');
    const qtyPlus = document.getElementById('qty-plus');
    if (qtyMinus && qtyPlus) {
      qtyMinus.addEventListener('click', () => {
        const q = this.quotes[this.selectedSymbol];
        const step = (q && q.lot_size) ? q.lot_size : 1;
        this.orderQty = Math.max(step, this.orderQty - step);
        if (qtyInput) qtyInput.value = this.orderQty;
        this.updateMarginSummary();
      });
      qtyPlus.addEventListener('click', () => {
        const q = this.quotes[this.selectedSymbol];
        const step = (q && q.lot_size) ? q.lot_size : 1;
        this.orderQty += step;
        if (qtyInput) qtyInput.value = this.orderQty;
        this.updateMarginSummary();
      });
    }

    // Execute Order Button
    const execBtn = document.getElementById('btn-execute-order');
    if (execBtn) {
      execBtn.addEventListener('click', () => this.submitOrder());
    }

    // Reset Portfolio Button
    const resetBtn = document.getElementById('btn-reset-portfolio');
    if (resetBtn) {
      resetBtn.addEventListener('click', () => {
        if (confirm("Reset paper trading portfolio balance back to ₹1,00,000 Base Capital?")) {
          this.resetPortfolio();
        }
      });
    }

    // Manual Auto Square-Off Button
    const sqBtn = document.getElementById('btn-manual-squareoff');
    if (sqBtn) {
      sqBtn.addEventListener('click', () => {
        if (confirm("Execute Mandatory 03:18 PM Intraday Auto Square-Off for all positions?")) {
          this.triggerAutoSquareOff();
        }
      });
    }
  }

  initShortcuts() {
    window.addEventListener('keydown', (e) => {
      if (['INPUT', 'SELECT', 'TEXTAREA'].includes(document.activeElement.tagName)) {
        if (e.key === 'Escape') document.activeElement.blur();
        if (e.key === 'Enter' && e.shiftKey) {
          e.preventDefault();
          this.submitOrder();
        }
        return;
      }

      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        const s = document.getElementById('search-input');
        if (s) s.focus();
      } else if (e.key === '1') {
        this.switchView('terminal');
      } else if (e.key === '2') {
        this.switchView('positions');
      } else if (e.key === '3') {
        this.switchView('radar');
      } else if (e.key === '4') {
        this.switchView('timemachine');
      } else if (e.key.toLowerCase() === 'b') {
        this.setSide('BUY');
      } else if (e.key.toLowerCase() === 's') {
        this.setSide('SELL');
      } else if (e.shiftKey && e.key === 'Enter') {
        this.submitOrder();
      }
    });
  }

  switchView(viewName) {
    this.currentView = viewName;

    const views = {
      'terminal': document.getElementById('view-terminal') || document.getElementById('main-terminal-grid'),
      'positions': document.getElementById('view-positions'),
      'radar': document.getElementById('view-radar'),
      'timemachine': document.getElementById('time-machine-fullpage')
    };

    const navTabs = {
      'terminal': document.getElementById('nav-btn-terminal'),
      'positions': document.getElementById('nav-btn-positions'),
      'radar': document.getElementById('nav-btn-radar'),
      'timemachine': document.getElementById('nav-btn-timemachine')
    };

    const ribbon = document.getElementById('ticker-ribbon');

    // Hide all views and deactivate tab styles
    Object.keys(views).forEach(key => {
      if (views[key]) views[key].style.display = 'none';
      if (navTabs[key]) navTabs[key].classList.remove('active');
    });

    if (navTabs[viewName]) {
      navTabs[viewName].classList.add('active');
    }

    if (viewName === 'terminal') {
      if (views['terminal']) views['terminal'].style.display = 'grid';
      if (ribbon) ribbon.style.display = 'flex';
      this.isTimeMachineOpen = false;
      this.stopReplayPolling();
      setTimeout(() => {
        if (this.chartManager) this.chartManager.resize();
      }, 60);
    } else if (viewName === 'timemachine') {
      if (views['timemachine']) views['timemachine'].style.display = 'block';
      if (ribbon) ribbon.style.display = 'none';
      this.openTimeMachineFullPage();
    } else if (viewName === 'positions') {
      if (views['positions']) views['positions'].style.display = 'block';
      if (ribbon) ribbon.style.display = 'none';
      this.isTimeMachineOpen = false;
      this.stopReplayPolling();
      this.loadPortfolio();
      this.loadSeats();
    } else if (viewName === 'radar') {
      if (views['radar']) views['radar'].style.display = 'block';
      if (ribbon) ribbon.style.display = 'none';
      this.isTimeMachineOpen = false;
      this.stopReplayPolling();
      this.loadSniperRadar();
    }

    this.playBeep(480, 'sine', 0.02);
  }

  setSide(side) {
    this.orderSide = side;
    const btnBuy = document.getElementById('side-buy');
    const btnSell = document.getElementById('side-sell');
    const execBtn = document.getElementById('btn-execute-order');

    if (side === 'BUY') {
      btnBuy.classList.add('active');
      btnSell.classList.remove('active');
      execBtn.className = 'btn-execute buy';
      execBtn.innerHTML = `BUY ${this.selectedSymbol.replace('.NS', '').replace('^', '')}`;
      this.playBeep(659, 'sine', 0.03);
    } else {
      btnSell.classList.add('active');
      btnBuy.classList.remove('active');
      execBtn.className = 'btn-execute sell';
      execBtn.innerHTML = `SELL ${this.selectedSymbol.replace('.NS', '').replace('^', '')}`;
      this.playBeep(440, 'sine', 0.03);
    }
    this.updateMarginSummary();
  }

  adjustQty(dir) {
    const q = this.quotes[this.selectedSymbol];
    const step = (q && q.lot_size) ? q.lot_size : 1;
    this.orderQty = Math.max(step, this.orderQty + (dir * step));
    const qtyInput = document.getElementById('order-qty-input');
    if (qtyInput) qtyInput.value = this.orderQty;
    this.updateMarginSummary();
    this.playBeep(700, 'sine', 0.02);
  }

  async startBootstrap() {
    this.showToast("Initializing Indian Market 9:15–3:30 Sniper Engine...", "info");
    
    // Fast parallel load of core telemetry so UI renders instantaneously
    await Promise.allSettled([
      this.loadSessionGate(),
      this.loadOverview(),
      this.loadTickers(),
      this.loadPortfolio(),
      this.loadSeats()
    ]);

    this.selectSymbol(this.selectedSymbol);

    // Non-blocking background load of sniper radar
    this.loadSniperRadar();

    // Live Clock loop
    setInterval(() => this.updateClock(), 1000);

    // Fast Ticker Refresh loop (every 1s)
    setInterval(() => this.pollLiveTicks(), 1000);

    // Ultra-Fast Portfolio & 2+2+2 Seats Live Sync Loop (every 800ms with zero lag)
    setInterval(() => {
      this.loadPortfolio();
      this.loadSeats();
    }, 800);

    // Quote Overview & Sniper Radar Background Refresh (every 15s)
    setInterval(() => {
      this.loadSessionGate();
      this.loadOverview();
      this.loadTickers(false);
    }, 15000);
  }

  updateClock() {
    const el = document.getElementById('live-clock');
    if (!el) return;
    const now = new Date();
    const options = { timeZone: 'Asia/Kolkata', hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' };
    el.textContent = `${now.toLocaleTimeString('en-GB', options)} IST`;
  }

  async loadSessionGate() {
    try {
      const res = await fetch('/api/sniper/session');
      const data = await res.json();
      this.sessionData = data;

      const badge = document.getElementById('sniper-session-badge');
      const text = document.getElementById('sniper-session-text');
      const dot = document.getElementById('market-status-dot');

      if (badge && text && data) {
        text.textContent = data.stage ? `${data.stage} (${data.session_note.split('(')[0].trim()})` : data.session_note;
        
        badge.className = 'sniper-gate-badge';
        if (data.stage === 'ACTIVE_SNIPER') {
          badge.classList.add('active-sniper');
          dot.className = 'status-dot live';
        } else if (data.stage === 'ORB_WARMUP') {
          badge.classList.add('orb-warmup');
          dot.className = 'status-dot closed';
        } else if (data.stage === 'AUTO_SQUARE_OFF') {
          badge.classList.add('auto-square-off');
          dot.className = 'status-dot closed';
        } else {
          dot.className = 'status-dot';
        }
      }
    } catch (e) {
      console.warn("Error loading session gate:", e);
    }
  }

  async loadOverview() {
    try {
      const res = await fetch('/api/overview');
      const data = await res.json();
      this.overviewData = data;

      // Update Ticker Ribbon
      const ribbon = document.getElementById('ticker-ribbon');
      if (ribbon && data.indices) {
        ribbon.innerHTML = data.indices.map(idx => `
          <div class="ticker-chip" onclick="window.terminal.selectSymbol('${idx.symbol}')">
            <span class="ticker-name">${idx.clean_symbol}</span>
            <span class="ticker-price num">₹${idx.ltp.toLocaleString('en-IN', {minimumFractionDigits: 2})}</span>
            <span class="ticker-change num ${idx.change >= 0 ? 'up' : 'down'}">
              ${idx.change >= 0 ? '▲ +' : '▼ '}${idx.change_pct.toFixed(2)}%
            </span>
          </div>
        `).join('');
      }

      // Update Market Breadth
      if (data.market_breadth) {
        const mb = data.market_breadth;
        document.getElementById('mb-adv').textContent = `${mb.advancers} (${mb.advancers_pct}%)`;
        document.getElementById('mb-dec').textContent = `${mb.decliners} (${mb.decliners_pct}%)`;
        document.getElementById('mb-ratio').textContent = `A/D: ${mb.advance_decline_ratio}`;
        document.getElementById('mb-bar-adv').style.width = `${mb.advancers_pct}%`;
        document.getElementById('mb-bar-dec').style.width = `${mb.decliners_pct}%`;
      }
    } catch (e) {
      console.warn("Error fetching overview:", e);
    }
  }

  async loadTickers(refreshList = true) {
    try {
      const res = await fetch('/api/tickers');
      const data = await res.json();
      data.forEach(item => {
        this.quotes[item.symbol] = item;
      });
      if (refreshList) {
        this.renderWatchlist();
      }
    } catch (e) {
      console.warn("Error fetching tickers:", e);
    }
  }

  renderWatchlist() {
    const container = document.getElementById('watchlist-container');
    if (!container) return;

    let items = Object.values(this.quotes);

    // Apply Filter
    if (this.activeFilter === 'nifty') {
      items = items.filter(x => x.type === 'index');
    } else if (this.activeFilter === 'banks') {
      items = items.filter(x => x.sector.includes('Bank') || x.clean_symbol === 'BANK NIFTY');
    } else if (this.activeFilter === 'tech') {
      items = items.filter(x => x.sector.includes('Tech') || x.clean_symbol === 'NIFTY IT');
    } else if (this.activeFilter === 'auto') {
      items = items.filter(x => x.sector.includes('Auto'));
    } else if (this.activeFilter === 'energy') {
      items = items.filter(x => x.sector.includes('Energy') || x.sector.includes('Power') || x.sector.includes('Oil'));
    } else if (this.activeFilter === 'gainers') {
      items = items.filter(x => x.change > 0).sort((a, b) => b.change_pct - a.change_pct);
    } else if (this.activeFilter === 'losers') {
      items = items.filter(x => x.change < 0).sort((a, b) => a.change_pct - b.change_pct);
    }

    container.innerHTML = items.map(stock => {
      const isActive = stock.symbol === this.selectedSymbol;
      const isUp = stock.change >= 0;
      const sparkSvg = this.generateSparkline(stock.sparkline, isUp);

      return `
        <div class="stock-row ${isActive ? 'active' : ''}" onclick="window.terminal.selectSymbol('${stock.symbol}')">
          <div class="stock-info">
            <div class="stock-sym">
              <span>${stock.clean_symbol}</span>
              <span class="sector-badge">${stock.exchange}</span>
            </div>
            <div class="stock-sub">${stock.name}</div>
          </div>
          <div class="stock-sparkline">${sparkSvg}</div>
          <div class="stock-price-col">
            <div class="stock-ltp num">₹${stock.ltp.toLocaleString('en-IN', {minimumFractionDigits: 2})}</div>
            <div class="stock-chg num ${isUp ? 'up' : 'down'}">
              ${isUp ? '+' : ''}${stock.change_pct.toFixed(2)}%
            </div>
          </div>
        </div>
      `;
    }).join('');
  }

  generateSparkline(points, isUp) {
    if (!points || points.length < 2) return '';
    const min = Math.min(...points);
    const max = Math.max(...points);
    const range = (max - min) || 1;
    const width = 50;
    const height = 18;

    const coords = points.map((p, idx) => {
      const x = (idx / (points.length - 1)) * width;
      const y = height - ((p - min) / range) * (height - 2) - 1;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');

    const strokeColor = isUp ? '#00e396' : '#ff4560';
    return `<svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
      <polyline fill="none" stroke="${strokeColor}" stroke-width="1.2" points="${coords}" />
    </svg>`;
  }

  filterWatchlist(query) {
    if (!query) {
      this.renderWatchlist();
      return;
    }
    const q = query.toLowerCase();
    const container = document.getElementById('watchlist-container');
    const items = Object.values(this.quotes).filter(x =>
      x.clean_symbol.toLowerCase().includes(q) ||
      x.name.toLowerCase().includes(q) ||
      x.sector.toLowerCase().includes(q)
    );

    container.innerHTML = items.map(stock => {
      const isActive = stock.symbol === this.selectedSymbol;
      const isUp = stock.change >= 0;
      const sparkSvg = this.generateSparkline(stock.sparkline, isUp);

      return `
        <div class="stock-row ${isActive ? 'active' : ''}" onclick="window.terminal.selectSymbol('${stock.symbol}')">
          <div class="stock-info">
            <div class="stock-sym">
              <span>${stock.clean_symbol}</span>
              <span class="sector-badge">${stock.exchange}</span>
            </div>
            <div class="stock-sub">${stock.name}</div>
          </div>
          <div class="stock-sparkline">${sparkSvg}</div>
          <div class="stock-price-col">
            <div class="stock-ltp num">₹${stock.ltp.toLocaleString('en-IN', {minimumFractionDigits: 2})}</div>
            <div class="stock-chg num ${isUp ? 'up' : 'down'}">
              ${isUp ? '+' : ''}${stock.change_pct.toFixed(2)}%
            </div>
          </div>
        </div>
      `;
    }).join('');
  }

  selectSymbol(symbol) {
    this.selectedSymbol = symbol;
    this.playBeep(520, 'sine', 0.03);

    document.querySelectorAll('.stock-row').forEach(row => {
      row.classList.remove('active');
    });

    const currentQuote = this.quotes[symbol];
    if (currentQuote) {
      document.getElementById('asset-title').textContent = currentQuote.clean_symbol;
      document.getElementById('asset-exchange').textContent = currentQuote.exchange;
      document.getElementById('asset-ltp').textContent = `₹${currentQuote.ltp.toLocaleString('en-IN', {minimumFractionDigits: 2})}`;

      const chgBadge = document.getElementById('asset-change');
      const isUp = currentQuote.change >= 0;
      chgBadge.className = `asset-chg-badge num ${isUp ? 'up' : 'down'}`;
      chgBadge.textContent = `${isUp ? '▲ +' : '▼ '}${currentQuote.change.toFixed(2)} (${currentQuote.change_pct.toFixed(2)}%)`;

      document.getElementById('tele-high').textContent = `₹${currentQuote.high.toLocaleString('en-IN', {minimumFractionDigits: 2})}`;
      document.getElementById('tele-low').textContent = `₹${currentQuote.low.toLocaleString('en-IN', {minimumFractionDigits: 2})}`;
      document.getElementById('tele-vol').textContent = currentQuote.volume.toLocaleString('en-IN');
      document.getElementById('tele-turnover').textContent = `₹${currentQuote.turnover_cr} Cr`;

      this.orderPrice = currentQuote.ltp;
      const priceInput = document.getElementById('order-price-input');
      if (priceInput) priceInput.value = currentQuote.ltp;

      const qtyInput = document.getElementById('order-qty-input');
      this.orderQty = currentQuote.lot_size || 25;
      if (qtyInput) qtyInput.value = this.orderQty;

      const execBtn = document.getElementById('btn-execute-order');
      if (execBtn) {
        execBtn.innerHTML = `${this.orderSide} ${currentQuote.clean_symbol}`;
      }

      this.updateMarginSummary();
    }

    // Clear and reload
    this.chartManager.clearSniperLevels();
    this.loadChart();
    this.loadDepth();
    this.loadTechnical();
  }

  async loadChart() {
    try {
      const res = await fetch(`/api/candles/${encodeURIComponent(this.selectedSymbol)}?timeframe=${this.selectedTimeframe}`);
      const data = await res.json();
      this.chartManager.renderData(data);
    } catch (e) {
      console.warn("Error loading candles:", e);
    }
  }

  async loadDepth() {
    try {
      const res = await fetch(`/api/depth/${encodeURIComponent(this.selectedSymbol)}`);
      const data = await res.json();
      this.renderDepth(data);
    } catch (e) {
      console.warn("Error loading depth:", e);
    }
  }

  renderDepth(depth) {
    const tableBody = document.getElementById('depth-table-body');
    if (!tableBody) return;

    document.getElementById('depth-spread').textContent = `SPREAD: ₹${depth.spread.toFixed(2)}`;
    document.getElementById('depth-buyers-pct').textContent = `${depth.buyer_pct}%`;
    document.getElementById('depth-sellers-pct').textContent = `${depth.seller_pct}%`;
    document.getElementById('depth-track-buyer').style.width = `${depth.buyer_pct}%`;
    document.getElementById('depth-track-seller').style.width = `${depth.seller_pct}%`;

    const maxBidVol = Math.max(...depth.bids.map(b => b.quantity), 1);
    const maxAskVol = Math.max(...depth.asks.map(a => a.quantity), 1);

    let html = '';
    for (let i = 0; i < 5; i++) {
      const bid = depth.bids[i] || {};
      const ask = depth.asks[i] || {};

      const bidBarW = ((bid.quantity || 0) / maxBidVol * 100).toFixed(0);
      const askBarW = ((ask.quantity || 0) / maxAskVol * 100).toFixed(0);

      html += `
        <tr>
          <td style="color: var(--text-muted);">${bid.orders || '-'}</td>
          <td>
            <div class="depth-bar-bid" style="width: ${bidBarW}%;"></div>
            <span class="depth-val">${(bid.quantity || 0).toLocaleString()}</span>
          </td>
          <td style="color: var(--bull-green); font-weight: 700;">₹${(bid.price || 0).toFixed(2)}</td>
          <td style="color: var(--bear-red); font-weight: 700;">₹${(ask.price || 0).toFixed(2)}</td>
          <td>
            <div class="depth-bar-ask" style="width: ${askBarW}%;"></div>
            <span class="depth-val">${(ask.quantity || 0).toLocaleString()}</span>
          </td>
          <td style="color: var(--text-muted);">${ask.orders || '-'}</td>
        </tr>
      `;
    }
    tableBody.innerHTML = html;
  }

  async loadTechnical() {
    try {
      const res = await fetch(`/api/technical/${encodeURIComponent(this.selectedSymbol)}`);
      const data = await res.json();
      this.renderTechnical(data);
    } catch (e) {
      console.warn("Error loading technical:", e);
    }
  }

  renderTechnical(tech) {
    const grid = document.getElementById('quant-copilot-grid');
    if (!grid) return;

    grid.innerHTML = `
      <div class="quant-card">
        <div class="quant-title">Pandas Quantitative Verdict</div>
        <div class="quant-val" style="color: ${tech.verdict.includes('BUY') ? 'var(--bull-green)' : (tech.verdict.includes('SELL') ? 'var(--bear-red)' : 'var(--accent-amber)')}">
          ${tech.verdict}
        </div>
        <div class="quant-desc">Trend: ${tech.trend}</div>
      </div>
      <div class="quant-card">
        <div class="quant-title">RSI (14) Momentum</div>
        <div class="quant-val num" style="color: ${tech.rsi > 70 ? 'var(--bear-red)' : (tech.rsi < 30 ? 'var(--bull-green)' : 'var(--accent-cyan)')}">
          ${tech.rsi.toFixed(2)}
        </div>
        <div class="quant-desc">${tech.rsi_status}</div>
      </div>
      <div class="quant-card">
        <div class="quant-title">Moving Averages (EMA)</div>
        <div class="quant-val num" style="font-size: 12.5px;">
          20 EMA: ₹${tech.ema20.toLocaleString()}
        </div>
        <div class="quant-desc">50 EMA: ₹${tech.ema50.toLocaleString()}</div>
      </div>
      <div class="quant-card">
        <div class="quant-title">Floor Trader Pivot Levels</div>
        <div class="quant-val num" style="font-size: 12px;">
          R1: ₹${tech.pivots.r1} | PP: ₹${tech.pivots.pivot}
        </div>
        <div class="quant-desc">S1: ₹${tech.pivots.s1} | R2: ₹${tech.pivots.r2}</div>
      </div>
    `;
  }

  // =========================================================================
  // 2+2+2 SEATS DASHBOARD & SNIPER RADAR
  // =========================================================================
  async loadSeats() {
    try {
      if (!this.portfolioData) {
        await this.loadPortfolio();
      }
      const res = await fetch('/api/sniper/seats');
      const data = await res.json();
      this.seatsData = data.seats || [];
      if (data.positions && data.positions.length > 0) {
        if (!this.portfolioData) this.portfolioData = {};
        this.portfolioData.positions = data.positions;
      }

      // Update Daily Goal Tracker in Top Bar
      const progEl = document.getElementById('header-target-progress');
      const barEl = document.getElementById('header-target-bar');
      if (progEl && barEl) {
        progEl.textContent = `${data.target_progress_pct}% (₹${data.total_pnl.toLocaleString('en-IN')})`;
        barEl.style.width = `${data.target_progress_pct}%`;
      }

      this.renderSeatsGrid();
    } catch (e) {
      console.warn("Error loading seats:", e);
    }
  }

  renderSeatsGrid() {
    const container = document.getElementById('seats-container');
    if (!container) return;

    if (!this.seatsData || this.seatsData.length === 0) {
      container.innerHTML = `<div style="grid-column: span 3; text-align: center; color: var(--text-muted); padding: 30px;">Initializing 2+2+2 Institutional Seats...</div>`;
      return;
    }

    container.innerHTML = this.seatsData.map((seat, idx) => {
      const isActive = seat.status === 'ACTIVE';
      const pos = this.portfolioData && this.portfolioData.positions ? 
        this.portfolioData.positions.find(p => p.seat_id === seat.seat_id || p.id === seat.active_position_id || (seat.active_position_id && p.symbol && seat.active_position_id.startsWith(p.symbol))) : null;

      let categoryLabel = 'Chopping Ping-Pong';
      let categoryColor = '#38bdf8';
      let categoryIcon = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#38bdf8" stroke-width="2"><polyline points="16 3 21 8 16 13"></polyline><line x1="21" y1="8" x2="9" y2="8"></line><polyline points="8 21 3 16 8 11"></polyline><line x1="3" y1="16" x2="15" y2="16"></line></svg>`;
      if (seat.category.includes('TREND')) {
        categoryLabel = 'Normal Trend Runner';
        categoryColor = '#00FFA3';
        categoryIcon = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#00FFA3" stroke-width="2"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"></polyline><polyline points="17 6 23 6 23 12"></polyline></svg>`;
      } else if (seat.category.includes('OPTION')) {
        categoryLabel = 'Index Option 0.60Δ Mirror';
        categoryColor = '#c084fc';
        categoryIcon = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#c084fc" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>`;
      }

      if (isActive && pos) {
        const isUp = pos.pnl >= 0;
        const totalDist = Math.abs((pos.tp_price || pos.avg_price * 1.02) - pos.avg_price);
        const currDist = Math.abs(pos.current_ltp - pos.avg_price);
        const runwayPct = totalDist > 0 ? Math.min(100, Math.max(5, (currDist / totalDist) * 100)) : 50;

        return `
          <div class="seat-card-spacious active-seat">
            <div>
              <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
                <span style="font-size: 11px; font-weight: 800; color: ${categoryColor}; display: flex; align-items: center; gap: 5px;">
                  <span>${categoryIcon}</span> <span>${seat.seat_id}</span>
                </span>
                <span class="seat-status-tag active">● ACTIVE IN TRADE</span>
              </div>
              <div style="font-size: 11px; color: var(--text-secondary); margin-bottom: 6px;">
                ${categoryLabel} • Min R:R 1:${seat.min_rr.toFixed(1)}
              </div>
              <div style="display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 4px;">
                <span style="font-size: 15px; font-weight: 800; color: #fff;">${pos.clean_symbol}</span>
                <span style="font-size: 11px; font-weight: 700; color: ${pos.side === 'BUY' ? 'var(--bull-green)' : 'var(--bear-red)'}; background: rgba(255,255,255,0.06); padding: 2px 6px; border-radius: 4px;">
                  ${pos.side} ${pos.quantity} Qty
                </span>
              </div>
              <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; font-size: 10.5px; font-family: var(--font-mono); margin-bottom: 8px;">
                <div><span style="color: var(--text-muted);">Entry:</span> <strong>₹${pos.avg_price.toFixed(1)}</strong></div>
                <div><span style="color: var(--text-muted);">LTP:</span> <strong style="color: #fff;">₹${pos.current_ltp.toFixed(1)}</strong></div>
                <div><span style="color: var(--text-muted);">Stage:</span> <strong style="color: ${categoryColor};">${pos.trailing_stage || 'HANDS_OFF'}</strong></div>
              </div>
              <div class="bracket-runway">
                <div class="bracket-labels">
                  <span style="color: var(--bear-red);">SL ₹${pos.sl_price ? pos.sl_price.toFixed(1) : '-'}</span>
                  <span style="color: var(--text-muted);">${runwayPct.toFixed(0)}% to TP</span>
                  <span style="color: var(--bull-green);">TP ₹${pos.tp_price ? pos.tp_price.toFixed(1) : '-'}</span>
                </div>
                <div class="bracket-track">
                  <div class="bracket-progress" style="width: ${runwayPct}%;"></div>
                </div>
              </div>
            </div>
            <div style="display: flex; align-items: center; justify-content: space-between; margin-top: 12px; padding-top: 8px; border-top: 1px solid rgba(255,255,255,0.06);">
              <div>
                <span style="font-size: 9.5px; color: var(--text-muted); display: block;">Floating P&L</span>
                <span class="num" style="font-size: 15px; font-weight: 800; color: ${isUp ? 'var(--bull-green)' : 'var(--bear-red)'};">
                  ${isUp ? '+' : ''}₹${pos.pnl.toFixed(2)} (${pos.pnl_pct.toFixed(2)}%)
                </span>
              </div>
              <button class="action-btn-sm" style="background: rgba(255,69,96,0.15); border-color: rgba(255,69,96,0.4); color: #ff4560; font-weight: 700; padding: 5px 12px; cursor: pointer;" onclick="window.terminal.squareOff('${pos.id}', '${pos.symbol}')">
                Square Off
              </button>
            </div>
          </div>
        `;
      } else if (isActive) {
        return `
          <div class="seat-card-spacious active-seat" style="border-color: ${categoryColor};">
            <div>
              <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
                <span style="font-size: 11px; font-weight: 800; color: ${categoryColor}; display: flex; align-items: center; gap: 5px;">
                  <span>${categoryIcon}</span> <span>${seat.seat_id}</span>
                </span>
                <span class="seat-status-tag active">● ACTIVE IN TRADE</span>
              </div>
              <div style="font-size: 11px; color: var(--text-secondary); margin-bottom: 6px;">
                ${categoryLabel} • Min R:R 1:${seat.min_rr.toFixed(1)}
              </div>
              <div style="font-size: 14px; font-weight: 800; color: #fff; margin-bottom: 4px;">
                ${seat.active_position_id ? seat.active_position_id.replace('.NS_MIS', '').replace('_MIS', '') : 'Position Active'}
              </div>
              <div style="font-size: 11px; color: var(--text-muted);">
                Synchronizing live position telemetry...
              </div>
            </div>
          </div>
        `;
      } else {
        return `
          <div class="seat-card-spacious vacant-seat">
            <div>
              <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
                <span style="font-size: 11px; font-weight: 800; color: ${categoryColor}; display: flex; align-items: center; gap: 5px;">
                  <span>${categoryIcon}</span> <span>${seat.seat_id}</span>
                </span>
                <span class="seat-status-tag" style="border-color: rgba(255,255,255,0.15); color: var(--text-muted);">READY TO FIRE</span>
              </div>
              <div style="font-size: 12px; font-weight: 700; color: #fff; margin-bottom: 4px;">
                ${categoryLabel}
              </div>
              <div style="font-size: 11px; color: var(--text-muted); line-height: 1.4;">
                ${seat.category.includes('CHOP') ? 'Range-bound oscillating stocks sweeps VWAP/Bollinger bands' : seat.category.includes('TREND') ? 'High-momentum ORB breakouts and VWAP pullback continuations' : 'Ultra-high-conviction index signals automatically bought as ATM 0.60Δ Call/Put options'}
              </div>
            </div>
            <div style="display: flex; align-items: center; justify-content: space-between; margin-top: 12px; padding-top: 8px; border-top: 1px dashed rgba(255,255,255,0.08);">
              <span style="font-size: 10.5px; font-family: var(--font-mono); color: var(--text-secondary);">
                Required R:R = <strong style="color: #fff;">1 : ${seat.min_rr.toFixed(1)}</strong>
              </span>
              <span style="font-size: 10px; color: var(--text-dim); font-family: var(--font-mono);">
                Max Risk: ₹2,500 / lot
              </span>
            </div>
          </div>
        `;
      }
    }).join('');
  }

  async loadSniperRadar() {
    try {
      const res = await fetch('/api/sniper/scan');
      const data = await res.json();
      this.sniperSignals = data.signals || [];
      this.renderSniperRadar();
    } catch (e) {
      console.warn("Error loading sniper radar:", e);
    }
  }

  renderSniperRadar() {
    const container = document.getElementById('sniper-radar-container');
    const navRadarCount = document.getElementById('nav-radar-count');
    if (navRadarCount) navRadarCount.textContent = (this.sniperSignals || []).length;

    if (!container) return;

    if (!this.sniperSignals || this.sniperSignals.length === 0) {
      container.innerHTML = `
        <div style="grid-column: span 3; text-align: center; color: var(--text-muted); padding: 30px;">
          Scanning NSE F&O universe... 5-layer institutional filter active.
        </div>
      `;
      return;
    }

    container.innerHTML = this.sniperSignals.map(sig => {
      const isBuy = sig.action === 'BUY';
      return `
        <div class="sniper-card">
          <div class="sniper-card-top">
            <div class="sniper-sym-title">
              <span>${sig.clean_symbol}</span>
              <span class="sector-badge">${sig.seat_category.replace('_SEAT', '').replace(/_/g, ' ')}</span>
            </div>
            <div class="score-badge high">
              ★ ${sig.confluence_score}/100
            </div>
          </div>

          <div class="setup-tag">${sig.setup_name}</div>

          <div class="sniper-metric-grid">
            <div class="metric-box">
              <span class="metric-lbl">Entry</span>
              <span class="metric-val num" style="color: var(--accent-cyan);">₹${sig.entry_price.toFixed(2)}</span>
            </div>
            <div class="metric-box">
              <span class="metric-lbl">Tight SL</span>
              <span class="metric-val num" style="color: var(--bear-red);">₹${sig.sl_price.toFixed(2)}</span>
            </div>
            <div class="metric-box">
              <span class="metric-lbl">Pre-Rev TP</span>
              <span class="metric-val num" style="color: var(--bull-green);">₹${sig.tp_price.toFixed(2)}</span>
            </div>
          </div>

          <div style="display: flex; justify-content: space-between; font-size: 10px; color: var(--text-secondary);">
            <span>R:R = <strong style="color: var(--text-primary); font-family: var(--font-mono);">1 : ${sig.rr_ratio}</strong></span>
            <span>Max Risk: <strong style="color: var(--bear-red); font-family: var(--font-mono);">₹${sig.max_risk_inr}</strong></span>
            <span>Profit: <strong style="color: var(--bull-green); font-family: var(--font-mono);">+₹${sig.expected_profit_inr}</strong></span>
          </div>

          ${sig.recommended_strike ? `
            <div class="option-mirror-box">
              <span>⚡ Option Mirror: <strong>${sig.clean_symbol} ${sig.recommended_strike} ${sig.action === 'BUY' ? 'CE' : 'PE'}</strong> (0.60 Delta)</span>
            </div>
          ` : ''}

          <div style="display: flex; gap: 6px; margin-top: 4px;">
            <button class="btn-sniper-arm ${isBuy ? 'buy' : 'sell'}" style="flex: 1;" onclick="window.terminal.armAndSnipeByIndex(${idx})">
              ARM & SNIPE (${sig.action})
            </button>
            <button class="btn-icon" title="View on Chart" onclick="window.terminal.previewSignalByIndex(${idx})">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                <circle cx="12" cy="12" r="3"></circle>
              </svg>
            </button>
          </div>
        </div>
      `;
    }).join('');
  }

  armAndSnipeByIndex(idx) {
    const sig = this.sniperSignals && this.sniperSignals[idx];
    if (sig) this.armAndSnipe(sig);
  }

  previewSignalByIndex(idx) {
    const sig = this.sniperSignals && this.sniperSignals[idx];
    if (sig) this.previewSignalOnChart(sig.symbol, sig);
  }

  previewSignalOnChart(symbol, sig) {
    this.switchView('terminal');
    this.selectSymbol(symbol);
    this.chartManager.setSniperLevels({
      entryPrice: sig.entry_price,
      slPrice: sig.sl_price,
      tpPrice: sig.tp_price,
      firstReversalWallPrice: sig.first_reversal_wall_price,
      reversalWallSource: sig.reversal_wall_source
    });
    this.showToast(`Plotted Sniper Levels for ${sig.clean_symbol} on Chart!`, "info");
  }

  async armAndSnipe(signal) {
    this.previewSignalOnChart(signal.symbol, signal);

    try {
      const res = await fetch('/api/sniper/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol: signal.symbol, signal: signal })
      });
      const data = await res.json();

      if (res.ok && data.success) {
        this.playOrderSound(true);
        this.showToast(`🎯 SNIPED! ${signal.action} ${signal.quantity_lots_or_shares} ${signal.clean_symbol} into ${data.seat_id}`, 'success');
        await this.loadPortfolio();
        await this.loadSeats();
      } else {
        this.playOrderSound(false);
        this.showToast(data.detail || data.error || 'Sniper execution failed', 'error');
      }
    } catch (e) {
      this.playOrderSound(false);
      this.showToast("Network error executing sniper signal", "error");
    }
  }

  async triggerAutoSquareOff() {
    try {
      const res = await fetch('/api/sniper/auto-square-off', { method: 'POST' });
      const data = await res.json();
      this.playOrderSound(true);
      this.showToast(`Square-off complete! Closed ${data.squared_off_count} intraday seats.`, 'success');
      await this.loadPortfolio();
      await this.loadSeats();
    } catch (e) {
      this.showToast("Square-off failed", "error");
    }
  }

  updateMarginSummary() {
    const q = this.quotes[this.selectedSymbol];
    const price = this.orderType === 'MARKET' ? (q ? q.ltp : this.orderPrice) : (parseFloat(document.getElementById('order-price-input').value) || this.orderPrice);
    const turnover = price * this.orderQty;
    const mult = this.orderProduct === 'MIS' ? 0.20 : 1.0;
    const margin = turnover * mult;

    const brokerage = this.orderProduct === 'MIS' ? Math.min(20.0, turnover * 0.0003) : 0.0;
    const stt = this.orderProduct === 'CNC' ? turnover * 0.001 : (this.orderSide === 'SELL' ? turnover * 0.00025 : 0);
    const totalCharges = brokerage + stt + (turnover * 0.0000345) + (turnover * 0.00015) + (brokerage * 0.18);

    document.getElementById('margin-required').textContent = `₹${margin.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
    document.getElementById('tax-breakdown').textContent = `₹${totalCharges.toFixed(2)}`;
  }

  async submitOrder() {
    const q = this.quotes[this.selectedSymbol];
    const cleanSym = q ? q.clean_symbol : this.selectedSymbol;
    const priceVal = this.orderType === 'MARKET' ? (q ? q.ltp : this.orderPrice) : parseFloat(document.getElementById('order-price-input').value);
    const slVal = parseFloat(document.getElementById('order-sl-input').value) || null;
    const tpVal = parseFloat(document.getElementById('order-tp-input').value) || null;

    const payload = {
      symbol: this.selectedSymbol,
      clean_symbol: cleanSym,
      side: this.orderSide,
      order_type: this.orderType,
      product: this.orderProduct,
      quantity: this.orderQty,
      price: priceVal,
      sl_price: slVal,
      tp_price: tpVal
    };

    try {
      const res = await fetch('/api/orders/place', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();

      if (res.ok && data.success) {
        this.playOrderSound(true);
        this.showToast(`Order Executed! ${payload.side} ${payload.quantity} ${cleanSym} @ ₹${data.order.price}`, 'success');
        this.loadPortfolio();
        this.loadSeats();
        this.loadDepth();
      } else {
        this.playOrderSound(false);
        this.showToast(data.detail || data.error || 'Order execution failed', 'error');
      }
    } catch (e) {
      this.playOrderSound(false);
      this.showToast("Network error submitting order", "error");
    }
  }

  async loadPortfolio() {
    try {
      const res = await fetch('/api/portfolio');
      const data = await res.json();
      this.portfolioData = data;

      const availCash = data.available_margin || 100000;
      const totalPnl = data.total_pnl || 0;
      const totalPnlPct = data.total_pnl_pct || 0;
      const positions = data.positions || [];
      const orders = data.orders || [];

      // Header Mini Pills
      const headerCash = document.getElementById('header-available-cash');
      if (headerCash) headerCash.textContent = `₹${availCash.toLocaleString('en-IN', {minimumFractionDigits: 2})}`;

      const pnlEl = document.getElementById('header-total-pnl');
      if (pnlEl) {
        pnlEl.textContent = `${totalPnl >= 0 ? '+' : ''}₹${totalPnl.toLocaleString('en-IN', {minimumFractionDigits: 2})} (${totalPnlPct}%)`;
        pnlEl.className = `portfolio-val num ${totalPnl >= 0 ? 'positive' : 'negative'}`;
      }

      // Nav Tab Badges & Footer Counts
      const navPosCount = document.getElementById('nav-pos-count');
      if (navPosCount) navPosCount.textContent = positions.length;

      const footerPosCount = document.getElementById('footer-pos-count');
      if (footerPosCount) footerPosCount.textContent = positions.length;

      const footerSeatsCount = document.getElementById('footer-seats-active-count');
      if (footerSeatsCount) footerSeatsCount.textContent = `${positions.length}/6`;

      // Dedicated Positions Page Scorecards
      const pageMargin = document.getElementById('pos-page-avail-margin');
      if (pageMargin) pageMargin.textContent = `₹${availCash.toLocaleString('en-IN', {minimumFractionDigits: 2})}`;

      const pageEquity = document.getElementById('pos-page-equity');
      if (pageEquity) pageEquity.textContent = `₹${(data.total_equity || availCash).toLocaleString('en-IN', {minimumFractionDigits: 2})}`;

      const pageRealized = document.getElementById('pos-page-realized-pnl');
      if (pageRealized) {
        const rp = data.realized_pnl || 0;
        pageRealized.textContent = `${rp >= 0 ? '+' : ''}₹${rp.toLocaleString('en-IN', {minimumFractionDigits: 2})}`;
        pageRealized.className = `num ${rp >= 0 ? 'up' : 'down'}`;
      }

      const pageFloating = document.getElementById('pos-page-floating-pnl');
      if (pageFloating) {
        const fp = data.unrealized_pnl || 0;
        pageFloating.textContent = `${fp >= 0 ? '+' : ''}₹${fp.toLocaleString('en-IN', {minimumFractionDigits: 2})}`;
        pageFloating.className = `num ${fp >= 0 ? 'up' : 'down'}`;
      }

      const pageTotalReturn = document.getElementById('pos-page-total-return');
      if (pageTotalReturn) {
        pageTotalReturn.textContent = `${totalPnl >= 0 ? '+' : ''}${totalPnlPct}% Net Return`;
        pageTotalReturn.style.color = totalPnl >= 0 ? 'var(--bull-green)' : 'var(--bear-red)';
      }

      const pageGoalPct = document.getElementById('pos-page-goal-pct');
      const pageGoalBar = document.getElementById('pos-page-goal-bar');
      const goalPct = data.target_progress_pct || 0;
      if (pageGoalPct) pageGoalPct.textContent = `${goalPct.toFixed(1)}%`;
      if (pageGoalBar) pageGoalBar.style.width = `${Math.min(100, Math.max(0, goalPct))}%`;

      const pageOpenCnt = document.getElementById('pos-page-open-cnt');
      if (pageOpenCnt) pageOpenCnt.textContent = `${positions.length} Open Seats`;

      const pageClosedCnt = document.getElementById('pos-page-closed-cnt');
      if (pageClosedCnt) pageClosedCnt.textContent = `${orders.length} Closed Trades`;

      const pageOpenTbl = document.getElementById('pos-page-open-table-count');
      if (pageOpenTbl) pageOpenTbl.textContent = `${positions.length} Open Positions`;

      const pageClosedTbl = document.getElementById('pos-page-closed-table-count');
      if (pageClosedTbl) pageClosedTbl.textContent = `${orders.length} Trades Logged`;

      this.renderPositionsTable(positions);
      this.renderOrdersTable(orders);
      this.renderSeatsGrid();
    } catch (e) {
      console.warn("Error fetching portfolio:", e);
    }
  }

  renderPositionsTable(positions) {
    const tbody = document.getElementById('positions-table-body');
    if (!tbody) return;

    if (!positions || positions.length === 0) {
      tbody.innerHTML = `<tr><td colspan="11" style="text-align: center; color: var(--text-muted); padding: 24px;">No active open positions in 2+2+2 seats.</td></tr>`;
      return;
    }

    tbody.innerHTML = positions.map(p => `
      <tr>
        <td style="font-weight: 700; color: #fff;">${p.clean_symbol}</td>
        <td><span class="sector-badge" style="color: ${p.side === 'BUY' ? 'var(--bull-green)' : 'var(--bear-red)'}">${p.seat_id || 'MIS'} ${p.side}</span></td>
        <td><span style="font-weight: 700; color: ${p.side === 'BUY' ? 'var(--bull-green)' : 'var(--bear-red)'};">${p.side}</span></td>
        <td>${p.quantity}</td>
        <td>
          <div style="font-weight: 700; color: #fff;">₹${p.avg_price.toFixed(2)}</div>
          <div style="font-size: 9.5px; color: var(--text-muted);">Amt: ₹${(p.avg_price * p.quantity).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div>
        </td>
        <td>
          <div style="font-weight: 700; color: #fff;">₹${p.current_ltp.toFixed(2)}</div>
          <div style="font-size: 9.5px; color: var(--text-muted);">Val: ₹${(p.current_ltp * p.quantity).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div>
        </td>
        <td style="color: var(--bear-red); font-weight: 600;">${p.sl_price ? '₹' + p.sl_price.toFixed(2) : '-'}</td>
        <td style="color: var(--bull-green); font-weight: 600;">${p.tp_price ? '₹' + p.tp_price.toFixed(2) : '-'}</td>
        <td style="font-size: 10.5px; color: var(--accent-cyan); font-family: var(--font-mono);">${p.trailing_stage || 'HANDS_OFF'}</td>
        <td class="num ${p.is_positive ? 'up' : 'down'}" style="text-align: right; font-weight: 700;">
          ${p.is_positive ? '+' : ''}₹${p.pnl.toFixed(2)} (${p.pnl_pct.toFixed(2)}%)
        </td>
        <td style="text-align: right;">
          <button class="action-btn-sm" style="background: rgba(255,69,96,0.15); border-color: rgba(255,69,96,0.4); color: #ff4560; font-weight: 700; padding: 4px 10px; cursor: pointer;" onclick="window.terminal.squareOff('${p.id}', '${p.symbol}')">Square Off</button>
        </td>
      </tr>
    `).join('');
  }

  renderOrdersTable(orders) {
    const tbody = document.getElementById('orders-table-body');
    if (!tbody) return;

    if (!orders || orders.length === 0) {
      tbody.innerHTML = `<tr><td colspan="11" style="text-align: center; color: var(--text-muted); padding: 24px;">No trades logged yet.</td></tr>`;
      return;
    }

    tbody.innerHTML = orders.map(o => {
      const isWin = (o.realized_pnl || 0) >= 0;
      const pnlDisplay = o.realized_pnl !== undefined && o.realized_pnl !== null ? `${isWin ? '+' : ''}₹${o.realized_pnl.toFixed(2)}` : '-';
      const exitPriceDisplay = o.exit_price ? `₹${o.exit_price.toFixed(2)}` : '-';
      const filledAmount = o.filled_amount != null ? o.filled_amount : ((o.price || 0) * (o.quantity || 1));
      const filledDisplay = `₹${filledAmount.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;

      return `
        <tr>
          <td><span style="color: var(--text-muted);">${o.order_id}</span> <div style="font-size: 9.5px; color: var(--text-dim);">${o.timestamp}</div></td>
          <td style="font-weight: 700; color: #fff;">${o.clean_symbol}</td>
          <td><span class="sector-badge">${o.seat_id || 'DESK'}</span></td>
          <td><span style="color: ${o.side === 'BUY' ? 'var(--bull-green)' : 'var(--bear-red)'}; font-weight: 700;">${o.side}</span></td>
          <td>${o.product} ${o.order_type}</td>
          <td>${o.quantity}</td>
          <td>₹${o.price.toFixed(2)}</td>
          <td style="font-weight: 800; color: #00FFA3;">${filledDisplay}</td>
          <td>${exitPriceDisplay}</td>
          <td class="num ${isWin ? 'up' : 'down'}" style="text-align: right; font-weight: 700;">${pnlDisplay}</td>
          <td style="text-align: right;"><span style="color: var(--bull-green); font-size: 11px;">● ${o.status}</span></td>
        </tr>
      `;
    }).join('');
  }

  async squareOff(posId, symbol) {
    try {
      const pos = (this.positions || []).find(p => p.id === posId || p.symbol === symbol);
      const exitPrice = pos ? pos.current_ltp : undefined;
      const res = await fetch('/api/orders/square-off', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ position_id: posId, symbol: symbol, price: exitPrice })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        this.playOrderSound(true);
        this.showToast(`Squared Off position in ${symbol.replace('.NS','')}`, 'success');
        await this.loadPortfolio();
        await this.loadSeats();
      } else {
        this.playOrderSound(false);
        this.showToast(data.detail || "Square off failed", "error");
      }
    } catch (e) {
      this.showToast("Network error squaring off", "error");
    }
  }

  async resetPortfolio() {
    try {
      await fetch('/api/portfolio/reset', { method: 'POST' });
      this.playOrderSound(true);
      this.showToast("Portfolio reset to ₹1,00,000 Base Capital", "success");
      await this.loadPortfolio();
      await this.loadSeats();
    } catch (e) {
      this.showToast("Reset failed", "error");
    }
  }

  async pollLiveTicks() {
    try {
      const res = await fetch('/api/live-ticks');
      const ticks = await res.json();

      if (ticks[this.selectedSymbol]) {
        const t = ticks[this.selectedSymbol];
        const elLtp = document.getElementById('asset-ltp');
        if (elLtp) {
          elLtp.textContent = `₹${t.ltp.toLocaleString('en-IN', {minimumFractionDigits: 2})}`;
        }
      }
    } catch (e) {}
  }

  switchDrawerTab(tabId) {
    const panes = ['seats', 'radar', 'positions', 'orders', 'quant', 'heatmap'];
    panes.forEach(p => {
      const el = document.getElementById(`pane-${p}`);
      if (el) el.style.display = tabId === p ? 'block' : 'none';
    });
    const paneHist = document.getElementById('pane-historical');
    if (paneHist) paneHist.style.display = tabId === 'historical' ? 'block' : 'none';

    // Update active tab visually
    document.querySelectorAll('.d-tab').forEach(t => {
      if (t.dataset.drawer === tabId) {
        t.classList.add('active');
      } else if (t.id !== 'tab-launch-time-machine') {
        t.classList.remove('active');
      }
    });

    if (tabId === 'heatmap') {
      this.renderHeatmap();
    } else if (tabId === 'radar') {
      this.loadSniperRadar();
    } else if (tabId === 'seats') {
      this.loadSeats();
    }
  }

  async loadHistoricalDashboard() {
    try {
      const res = await fetch('/api/historical/overview');
      if (!res.ok) return;
      const data = await res.json();

      // Update date range
      const dateRangeEl = document.getElementById('hist-date-range');
      if (dateRangeEl && data.date_range) {
        dateRangeEl.innerText = `${data.date_range} • ${Number(data.total_candles || 21014).toLocaleString('en-IN')} Candles`;
      }

      // Populate 14 cached symbols chips
      const symContainer = document.getElementById('hist-symbols-container');
      if (symContainer && Array.isArray(data.symbols)) {
        symContainer.innerHTML = data.symbols.map(s => {
          const symName = typeof s === 'string' ? s : s.symbol;
          const isSelected = this.selectedSymbol.includes(symName) || (symName === 'NIFTY' && this.selectedSymbol === '^NSEI');
          return `
            <button class="action-btn-sm btn-hist-sym" data-sym="${symName}" style="font-size: 10px; font-weight: 700; padding: 4px 8px; cursor: pointer; border-radius: 4px; ${
              isSelected
                ? 'background: rgba(0, 255, 163, 0.25); color: #00FFA3; border: 1px solid rgba(0, 255, 163, 0.6); box-shadow: 0 0 8px rgba(0, 255, 163, 0.3);'
                : 'background: var(--bg-surface); color: var(--text-secondary); border: 1px solid var(--border-medium);'
            }">
              ${symName} <span style="font-size: 8px; color: var(--text-muted);">(1501 15m)</span>
            </button>
          `;
        }).join('');

        // Wire click on symbol chips to plot on chart
        symContainer.querySelectorAll('.btn-hist-sym').forEach(btn => {
          btn.addEventListener('click', (e) => {
            const sym = e.currentTarget.dataset.sym;
            let fullSym = sym;
            if (sym === 'NIFTY') fullSym = '^NSEI';
            else if (sym === 'BANKNIFTY') fullSym = '^NSEBANK';
            else if (sym === 'SENSEX') fullSym = '^BSESN';
            else if (sym === 'FINNIFTY') fullSym = 'NIFTY_FIN_SERVICE.NS';
            else if (!fullSym.endsWith('.NS')) fullSym = `${fullSym}.NS`;

            this.selectedSymbol = fullSym;
            this.selectedTimeframe = '60D';

            // Update timeframe active pill
            document.querySelectorAll('.tf-btn').forEach(b => {
              b.classList.toggle('active', b.dataset.tf === '60D');
            });

            this.loadChart();
            this.loadHistoricalDashboard();
            this.playBeep(520, 'sine', 0.03);
          });
        });
      }

      // Populate Closed Trades Table
      const tradesBody = document.getElementById('hist-trades-table-body');
      if (tradesBody && Array.isArray(data.recent_trades)) {
        if (data.recent_trades.length === 0) {
          tradesBody.innerHTML = '<tr><td colspan="10" style="text-align: center; color: var(--text-muted); padding: 20px;">No closed trades logged yet.</td></tr>';
          return;
        }

        tradesBody.innerHTML = data.recent_trades.map(t => {
          const isWin = (t.pnlInr || 0) >= 0;
          const exitReason = t.exitReason || 'TARGET_TP_HIT';

          const reasonBadgeStyle = exitReason === 'TARGET_TP_HIT'
            ? 'background: rgba(0, 227, 150, 0.15); color: #00FFA3; border: 1px solid rgba(0, 227, 150, 0.4);'
            : exitReason === 'PROFIT_LOCKED_EXIT'
            ? 'background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.4);'
            : exitReason === 'BREAKEVEN_SCRATCH_EXIT'
            ? 'background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.4);'
            : exitReason === 'INTRADAY_AUTO_SQUARE_OFF'
            ? 'background: rgba(168, 85, 247, 0.15); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.4);'
            : 'background: rgba(255, 69, 96, 0.15); color: #ff4560; border: 1px solid rgba(255, 69, 96, 0.4);';

          const reasonLabel = exitReason === 'TARGET_TP_HIT' ? '🎯 TP WALL'
            : exitReason === 'PROFIT_LOCKED_EXIT' ? '🔒 55% PROFIT LOCK'
            : exitReason === 'BREAKEVEN_SCRATCH_EXIT' ? '⚖️ BREAKEVEN'
            : exitReason === 'INTRADAY_AUTO_SQUARE_OFF' ? '⏰ 03:18 PM EXIT'
            : '🛡️ INVALIDATION SL';

          const actionClass = t.action === 'BUY' ? 'style="color: var(--bull-green); font-weight: 700;"' : 'style="color: var(--bear-red); font-weight: 700;"';
          const seatShort = t.seatCategory === 'CHOP_PING_PONG_SEAT' ? 'CHOP'
            : t.seatCategory === 'NORMAL_TREND_RUNNER_SEAT' ? 'TREND'
            : 'OPTION (0.60Δ)';

          return `
            <tr>
              <td style="font-family: 'JetBrains Mono', monospace; font-size: 10px; color: var(--text-muted);">${t.id}</td>
              <td style="font-size: 10px; color: var(--text-secondary);">${t.entryDateStr || ''} ${t.entryTimeStr || ''}</td>
              <td style="font-weight: 800; color: #fff;">
                ${t.symbol} ${t.isOption ? `<span style="font-size: 9px; color: #fbbf24;">${t.strike || ''}</span>` : ''}
              </td>
              <td ${actionClass}>${t.action}</td>
              <td style="font-size: 9px; font-family: 'JetBrains Mono', monospace; color: var(--text-muted);">${seatShort}</td>
              <td class="num">₹${Number(t.entryPrice).toLocaleString('en-IN', {minimumFractionDigits: 1, maximumFractionDigits: 1})}</td>
              <td class="num">₹${Number(t.exitPrice).toLocaleString('en-IN', {minimumFractionDigits: 1, maximumFractionDigits: 1})}</td>
              <td class="num" style="font-weight: 800; color: ${isWin ? '#00FFA3' : '#ff4560'};">
                ${isWin ? '+' : ''}₹${Number(t.pnlInr).toLocaleString('en-IN')}
              </td>
              <td class="num" style="color: ${isWin ? '#00FFA3' : '#ff4560'};">
                ${isWin ? '+' : ''}${Number(t.roePct).toFixed(2)}%
              </td>
              <td>
                <span style="font-size: 8.5px; font-weight: 700; padding: 2px 6px; border-radius: 4px; text-transform: uppercase; ${reasonBadgeStyle}">
                  ${reasonLabel}
                </span>
              </td>
            </tr>
          `;
        }).join('');
      }

    } catch (e) {
      console.error('[HistoricalDashboard] Load error:', e);
    }
  }


  // =========================================================================
  // ⏳ FULL-PAGE INTERACTIVE PAST-DATE TIME-MACHINE SIMULATOR
  // =========================================================================
  async openTimeMachineFullPage() {
    this.isTimeMachineOpen = true;
    const grid = document.getElementById('view-terminal') || document.getElementById('main-terminal-grid');
    const ribbon = document.getElementById('ticker-ribbon');
    const tmPage = document.getElementById('time-machine-fullpage');
    const posPage = document.getElementById('view-positions');
    const radPage = document.getElementById('view-radar');

    if (grid) grid.style.display = 'none';
    if (posPage) posPage.style.display = 'none';
    if (radPage) radPage.style.display = 'none';
    if (ribbon) ribbon.style.display = 'none';
    if (tmPage) {
      tmPage.style.display = 'block';
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    const tabTM = document.getElementById('nav-btn-timemachine');
    if (tabTM) {
      document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
      tabTM.classList.add('active');
    }

    this.playBeep(659, 'triangle', 0.08);

    // Load available 60 days for dropdown
    await this.loadReplayDays();

    // Fetch live state and start fast polling
    await this.fetchReplayState();
    this.startReplayPolling();
  }

  async loadReplayDays() {
    try {
      const res = await fetch('/api/replay/days');
      if (!res.ok) return;
      const data = await res.json();
      const select = document.getElementById('tm-date-select');
      if (select && data.days) {
        const curSelected = (this.replayState && this.replayState.currentDate) || data.currentDate || select.value;
        select.innerHTML = data.days.map(d => {
          const chgStr = d.niftyChangePct >= 0 ? `+${d.niftyChangePct}%` : `${d.niftyChangePct}%`;
          return `<option value="${d.date}" ${d.date === curSelected ? 'selected' : ''}>
            ${d.displayDate} • NIFTY ${Number(d.niftyClose).toLocaleString('en-IN')} (${chgStr}) • ${d.category}
          </option>`;
        }).join('');
        select.value = curSelected;
      }
    } catch (e) {
      console.warn("Error loading replay days:", e);
    }
  }

  async applySelectedDate(targetDate) {
    const select = document.getElementById('tm-date-select');
    const dateToLoad = targetDate || (select ? select.value : '2026-11-13');
    if (select && targetDate) {
      select.value = targetDate;
    }

    this.playBeep(784, 'triangle', 0.08);
    this.showToast(`⏳ Loading ${dateToLoad} from 09:15:00 AM IST sharp...`, "info");

    try {
      const res = await fetch('/api/replay/set-date', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          date: dateToLoad,
          auto_play: true,
          speed: this.replaySpeed || 5
        })
      });
      if (res.ok) {
        const data = await res.json();
        const state = data.state || data;
        this.replayState = state;
        this.renderTimeMachinePage(state);
        this.showToast(`🚀 Started Day Replay for ${state.currentDate} at 09:15:00 AM IST!`, "success");
      }
    } catch (e) {
      console.error("Failed to set replay date:", e);
    }
  }

  exitTimeMachineFullPage() {
    this.switchView('terminal');
    this.playBeep(440, 'sine', 0.05);
    this.showToast("Exited Time-Machine. Returned to Live Indian Market Terminal.", "info");
  }

  startReplayPolling() {
    this.stopReplayPolling();
    // Fast polling every 120ms for smooth second-by-second ticking
    this.replayPollingTimer = setInterval(async () => {
      if (this.isTimeMachineOpen) {
        await this.fetchReplayState();
      }
    }, 120);
    this.fetchReplayState();
  }

  stopReplayPolling() {
    if (this.replayPollingTimer) {
      clearInterval(this.replayPollingTimer);
      this.replayPollingTimer = null;
    }
  }

  async sendReplayControl(action, payload = {}) {
    try {
      if (action === 'SET_SPEED' && payload.speed) {
        this.replaySpeed = payload.speed;
      }
      const res = await fetch('/api/replay/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, ...payload })
      });
      if (res.ok) {
        const data = await res.json();
        const state = data.state || data;
        this.replayState = state;
        this.renderTimeMachinePage(state);
      }
    } catch (e) {
      console.warn("Replay control error:", e);
    }
  }

  async fetchReplayState() {
    try {
      const res = await fetch('/api/replay/state');
      if (res.ok) {
        const data = await res.json();
        const state = data.state || data;
        this.replayState = state;
        this.renderTimeMachinePage(state);
      }
    } catch (e) {
      console.warn("Replay state fetch error:", e);
    }
  }

  renderTimeMachinePage(s) {
    if (!s) return;

    // 1. Digital Clock, Date Badge & Dynamic Session Gate
    const istClock = document.getElementById('tm-ist-clock');
    const dateBadge = document.getElementById('tm-date-badge');
    const gatePill = document.getElementById('tm-session-gate-pill');
    const descText = document.getElementById('tm-session-desc-text');
    const statusPill = document.getElementById('tm-status-pill');

    if (istClock) {
      istClock.textContent = `🕒 ${s.formattedTime || '09:15:00 AM IST'}`;
    }

    if (dateBadge && s.formattedDateTime) {
      const dPart = s.formattedDateTime.split(',')[0] || s.currentDate;
      dateBadge.textContent = `📅 ${dPart.toUpperCase()}`;
    }

    if (gatePill) {
      const gate = s.sessionGate || 'WARMUP';
      if (gate === 'WARMUP') {
        gatePill.textContent = `🟡 WARM-UP (09:15 - 09:25 AM)`;
        gatePill.style.color = '#fbbf24';
        gatePill.style.background = 'rgba(245, 158, 11, 0.15)';
        gatePill.style.border = '1px solid rgba(245, 158, 11, 0.4)';
      } else if (gate === 'SNIPER_ACTIVE') {
        gatePill.textContent = `🟢 ACTIVE SNIPER (09:25 - 03:10 PM)`;
        gatePill.style.color = '#00FFA3';
        gatePill.style.background = 'rgba(0, 255, 163, 0.15)';
        gatePill.style.border = '1px solid rgba(0, 255, 163, 0.4)';
      } else if (gate === 'EXIT_CONVERGENCE') {
        gatePill.textContent = `🟠 EXIT CONVERGENCE (03:10 - 03:18 PM)`;
        gatePill.style.color = '#f97316';
        gatePill.style.background = 'rgba(249, 115, 22, 0.15)';
        gatePill.style.border = '1px solid rgba(249, 115, 22, 0.4)';
      } else if (gate === 'AUTO_SQUAREOFF') {
        gatePill.textContent = `🔴 03:18 PM AUTO SQUARE-OFF`;
        gatePill.style.color = '#ff4560';
        gatePill.style.background = 'rgba(255, 69, 96, 0.15)';
        gatePill.style.border = '1px solid rgba(255, 69, 96, 0.4)';
      } else {
        gatePill.textContent = `⚪ 03:30 PM MARKET CLOSED`;
        gatePill.style.color = '#a855f7';
        gatePill.style.background = 'rgba(168, 85, 247, 0.15)';
        gatePill.style.border = '1px solid rgba(168, 85, 247, 0.4)';
      }
    }

    if (descText && s.sessionGateDescription) {
      descText.innerHTML = `<span>●</span> <span>${s.sessionGateDescription}</span>`;
    }

    if (statusPill) {
      if (s.isRunning) {
        statusPill.textContent = `🟢 REPLAY ACTIVE (${s.speed}x)`;
        statusPill.style.color = '#00FFA3';
        statusPill.style.background = 'rgba(0, 255, 163, 0.15)';
        statusPill.style.border = '1px solid rgba(0, 255, 163, 0.4)';
      } else {
        statusPill.textContent = `⏸ REPLAY PAUSED`;
        statusPill.style.color = '#fbbf24';
        statusPill.style.background = 'rgba(245, 158, 11, 0.15)';
        statusPill.style.border = '1px solid rgba(245, 158, 11, 0.4)';
      }
    }

    // 2. High-Precision Intraday Timeline Scrubber
    const scrubLabel = document.getElementById('tm-scrub-time-label');
    const secCounter = document.getElementById('tm-second-counter');
    const secSlider = document.getElementById('tm-second-slider');
    const progPctText = document.getElementById('tm-prog-pct-text');

    if (scrubLabel) scrubLabel.textContent = s.formattedTime || '09:15:00 AM IST';
    if (secCounter) secCounter.textContent = (s.secondOfDay || 0).toLocaleString('en-IN');
    if (secSlider && !secSlider.matches(':active')) {
      secSlider.value = s.secondOfDay || 0;
    }
    if (progPctText) progPctText.textContent = `${s.timelineProgressPct || 0}% of Trading Day`;

    // 3. Highlight Selected Speed Button
    document.querySelectorAll('.tm-speed-btn').forEach(btn => {
      const spd = parseInt(btn.dataset.speed);
      if (spd === s.speed) {
        btn.style.background = '#00FFA3';
        btn.style.color = '#000';
        btn.style.borderColor = '#00FFA3';
        btn.style.boxShadow = '0 0 10px rgba(0, 255, 163, 0.4)';
      } else {
        btn.style.background = 'rgba(255,255,255,0.06)';
        btn.style.color = spd >= 300 ? '#fbbf24' : 'var(--text-secondary)';
        btn.style.borderColor = spd >= 300 ? 'rgba(245, 158, 11, 0.4)' : 'var(--border-medium)';
        btn.style.boxShadow = 'none';
      }
    });

    // 4. Live Ticker Ribbon (All 14 Instruments with tick flash)
    const tickerStrip = document.getElementById('tm-live-ticker-strip');
    if (tickerStrip && s.livePrices) {
      const activeSyms = new Set((s.activePositions || []).map(p => p.symbol));
      const symbolsOrder = ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'SENSEX', 'RELIANCE', 'HDFCBANK', 'ICICIBANK', 'SBIN', 'INFY', 'TCS', 'TATAMOTORS', 'AXISBANK', 'LT', 'BAJFINANCE'];
      
      tickerStrip.innerHTML = symbolsOrder.map(sym => {
        const price = s.livePrices[sym] || 0.0;
        const dir = (s.priceDirections && s.priceDirections[sym]) || 'FLAT';
        const chgPct = (s.pricePctChanges && s.pricePctChanges[sym]) ? s.pricePctChanges[sym] : 0.0;
        const isUp = dir === 'UP' || chgPct > 0;
        const isDown = dir === 'DOWN' || chgPct < 0;
        const color = isUp ? '#00FFA3' : (isDown ? '#ff4560' : 'var(--text-secondary)');
        const arrow = isUp ? '▲' : (isDown ? '▼' : '●');
        const hasPos = activeSyms.has(sym);

        return `
          <div style="display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 6px; background: ${hasPos ? 'rgba(0, 255, 163, 0.14)' : 'rgba(255,255,255,0.03)'}; border: 1px solid ${hasPos ? 'rgba(0, 255, 163, 0.6)' : 'rgba(255,255,255,0.08)'}; ${hasPos ? 'box-shadow: 0 0 10px rgba(0, 255, 163, 0.3);' : ''}">
            <span style="font-weight: 800; font-size: 11px; color: ${hasPos ? '#00FFA3' : '#fff'};">${sym}</span>
            <span class="num" style="font-weight: 700; font-size: 11.5px; color: ${color};">
              ${arrow} ₹${Number(price).toLocaleString('en-IN', {minimumFractionDigits: 1, maximumFractionDigits: 2})}
            </span>
            <span style="font-size: 9px; font-weight: 700; color: ${color}; font-family: 'JetBrains Mono', monospace;">
              (${chgPct >= 0 ? '+' : ''}${chgPct.toFixed(2)}%)
            </span>
            ${hasPos ? '<span style="font-size: 8px; font-weight: 800; background: #00FFA3; color: #000; padding: 1px 4px; border-radius: 3px;">SEAT</span>' : ''}
          </div>
        `;
      }).join('');
    }

    // 5. Section C: Financial Scoreboard & Daily Target
    const w = s.wallet || {};
    const kpiBalance = document.getElementById('tm-kpi-balance');
    const kpiReturn = document.getElementById('tm-kpi-return-pct');
    const kpiRealized = document.getElementById('tm-kpi-realized');
    const kpiFloating = document.getElementById('tm-kpi-floating');
    const kpiOpenCount = document.getElementById('tm-kpi-open-count');
    const kpiWinrate = document.getElementById('tm-kpi-winrate');
    const targetProgressBar = document.getElementById('tm-target-progress-bar');
    const kpiTp = document.getElementById('tm-kpi-tp-cnt');
    const kpiLock = document.getElementById('tm-kpi-lock-cnt');
    const kpiSl = document.getElementById('tm-kpi-sl-cnt');

    if (kpiBalance) kpiBalance.textContent = `₹${Number(w.currentBalanceInr || 100000).toLocaleString('en-IN', {minimumFractionDigits: 2})}`;
    if (kpiReturn) {
      const netPct = (((w.currentBalanceInr || 100000) - (w.startingCapitalInr || 100000)) / (w.startingCapitalInr || 100000) * 100).toFixed(2);
      kpiReturn.textContent = `Day Return: ${netPct >= 0 ? '+' : ''}${netPct}%`;
      kpiReturn.style.color = netPct >= 0 ? '#00FFA3' : '#ff4560';
    }
    if (kpiRealized) {
      const r = w.netDayPnlInr || 0;
      kpiRealized.textContent = `${r >= 0 ? '+' : ''}₹${Number(r).toLocaleString('en-IN', {minimumFractionDigits: 2})}`;
      kpiRealized.style.color = r >= 0 ? '#00FFA3' : '#ff4560';
    }
    if (targetProgressBar) {
      targetProgressBar.style.width = `${Math.min(100, w.targetProgressPct || 0)}%`;
      targetProgressBar.style.background = (w.netDayPnlInr || 0) >= 20000 ? '#00FFA3' : ((w.netDayPnlInr || 0) > 0 ? '#38bdf8' : '#ff4560');
    }
    if (kpiFloating) {
      const fl = w.floatingPnlInr || 0;
      kpiFloating.textContent = `${fl >= 0 ? '+' : ''}₹${Number(fl).toLocaleString('en-IN', {minimumFractionDigits: 2})}`;
      kpiFloating.style.color = fl >= 0 ? '#00FFA3' : '#ff4560';
    }
    if (kpiOpenCount) kpiOpenCount.textContent = `${(s.activePositions || []).length} Open Concurrent Seats (6 Cap)`;
    if (kpiWinrate) {
      const wr = w.winRatePct || 0;
      kpiWinrate.textContent = `${wr.toFixed(1)}%`;
      kpiWinrate.style.color = wr >= 50 ? '#00FFA3' : '#fbbf24';
    }
    if (kpiTp) kpiTp.textContent = `🎯 ${(w.tp4Hits || 0) + (w.tp5Hits || 0) + (w.tp6Hits || 0)} Runners (TP4-6)`;
    if (kpiLock) kpiLock.textContent = `🎯 ${(w.tp1Hits || 0) + (w.tp2Hits || 0) + (w.tp3Hits || 0)} Locks (TP1-3)`;
    if (kpiSl) kpiSl.textContent = `🛡️ ${w.smartSlHits || 0} Smart SL / ${w.maxLossCapHits || 0} Cap`;

    // 6. Section D: Live 2+2+2 Concurrent Seats
    const seatsCountBadge = document.getElementById('tm-active-seats-count');
    const posContainer = document.getElementById('tm-active-positions-container');
    const positions = s.activePositions || [];
    if (seatsCountBadge) seatsCountBadge.textContent = positions.length;

    if (posContainer) {
      const seatConfigs = [
        { label: 'SEAT 1 • CHOPPING PING-PONG', defaultDesc: 'VWAP / Bollinger Support Sweep Mean-Reversion' },
        { label: 'SEAT 2 • CHOPPING PING-PONG', defaultDesc: 'Range S&R Boundary Mean-Reversion' },
        { label: 'SEAT 3 • NORMAL TREND RUNNER', defaultDesc: 'Opening Range Breakout (ORB) Continuation' },
        { label: 'SEAT 4 • NORMAL TREND RUNNER', defaultDesc: 'High-Momentum EMA 9/21 Follow-Through' },
        { label: 'SEAT 5 • INDEX OPTION (0.60Δ)', defaultDesc: 'NIFTY / BANKNIFTY ITM Sniper Call/Put' },
        { label: 'SEAT 6 • INDEX OPTION (0.60Δ)', defaultDesc: 'Ultra-High Conviction Strike Runner' },
      ];

      posContainer.innerHTML = seatConfigs.map((cfg, idx) => {
        const pos = positions[idx];
        if (!pos) {
          return `
            <div style="background: rgba(255,255,255,0.02); border: 1px dashed rgba(255,255,255,0.12); border-radius: 10px; padding: 12px; display: flex; flex-direction: column; justify-content: center; min-height: 140px;">
              <div style="font-size: 10px; font-weight: 800; color: var(--text-muted); text-transform: uppercase; margin-bottom: 4px;">
                ${cfg.label}
              </div>
              <div style="font-size: 11px; color: var(--text-secondary); margin-bottom: 6px;">
                [SEAT VACANT]
              </div>
              <div style="font-size: 9.5px; color: var(--text-muted);">
                ${cfg.defaultDesc}
              </div>
            </div>
          `;
        }

        const isWin = (pos.floatingPnlInr || 0) >= 0;
        const progressPct = Math.max(0, Math.min(100, pos.progressPct || 0));
        const actionStr = pos.side || 'BUY';
        const actionColor = actionStr === 'BUY' ? 'var(--bull-green)' : 'var(--bear-red)';
        const seatName = pos.seatBucket || 'SEAT';

        return `
          <div style="background: #0f1621; border: 1px solid ${isWin ? 'rgba(0, 255, 163, 0.4)' : 'rgba(255, 69, 96, 0.4)'}; border-radius: 10px; padding: 12px; box-shadow: 0 4px 16px rgba(0,0,0,0.5);">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 6px;">
              <div>
                <div style="display: flex; align-items: center; gap: 6px;">
                  <span style="font-size: 13px; font-weight: 900; color: #fff;">${pos.symbol}</span>
                  ${pos.isOption ? `<span style="font-size: 10px; font-weight: 800; color: #fbbf24; background: rgba(245,158,11,0.15); padding: 1px 5px; border-radius: 3px;">${pos.optionType} ${pos.optionStrike || ''}</span>` : ''}
                  <span style="font-size: 9.5px; font-weight: 800; color: ${actionColor}; border: 1px solid ${actionColor}; padding: 1px 5px; border-radius: 3px;">
                    ${actionStr}
                  </span>
                </div>
                <div style="font-size: 9.5px; color: var(--text-muted); font-family: 'JetBrains Mono', monospace; margin-top: 2px;">
                  ${seatName} • ${pos.quantity} Qty
                </div>
              </div>

              <div style="text-align: right;">
                <div class="num" style="font-size: 15px; font-weight: 900; color: ${isWin ? '#00FFA3' : '#ff4560'};">
                  ${isWin ? '+' : ''}₹${Number(pos.floatingPnlInr || 0).toLocaleString('en-IN', {minimumFractionDigits: 1, maximumFractionDigits: 1})}
                </div>
                <div style="font-size: 9px; font-weight: 700; color: ${isWin ? '#00FFA3' : '#ff4560'};">
                  ${pos.stageNote || (pos.stage >= 6 ? '🎯 TP 6 TARGET BOOKED' : (pos.stage >= 1 ? `🎯 TP ${pos.stage} LOCKED` : 'RUNNING TO TP 1'))}
                </div>
              </div>
            </div>

            <!-- Price Telemetry: Entry -> Mark -> Trailing SL -->
            <div style="display: flex; justify-content: space-between; font-size: 10px; font-family: 'JetBrains Mono', monospace; margin-bottom: 6px; background: rgba(0,0,0,0.3); padding: 5px 8px; border-radius: 4px;">
              <div>
                <span style="color: var(--text-muted);">Entry:</span>
                <span style="color: #fff; font-weight: 700;">₹${Number(pos.entryPrice).toFixed(1)}</span>
              </div>
              <div>
                <span style="color: var(--text-muted);">Mark:</span>
                <span style="color: ${isWin ? '#00FFA3' : '#ff4560'}; font-weight: 700;">₹${Number(pos.currentPrice).toFixed(1)}</span>
              </div>
              <div>
                <span style="color: var(--text-muted);">Trail SL:</span>
                <span style="color: ${pos.stage >= 1 ? '#00FFA3' : '#ff4560'}; font-weight: 700;">₹${Number(pos.slPrice).toFixed(1)}</span>
              </div>
            </div>

            <!-- 6-Stage Scalper Ladder: 500 -> 1000 -> 1500 -> 2000 -> 2500 -> 3000 -->
            <div style="display: grid; grid-template-columns: repeat(6, 1fr); gap: 3px; margin-bottom: 6px;">
              <div style="padding: 3px 1px; text-align: center; border-radius: 4px; font-size: 8px; font-weight: 800; font-family: 'JetBrains Mono', monospace; ${pos.stage >= 1 ? 'background: rgba(0, 255, 163, 0.2); color: #00FFA3; border: 1px solid rgba(0, 255, 163, 0.5);' : (pos.stage === 0 ? 'background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px dashed rgba(56, 189, 248, 0.5);' : 'background: rgba(255,255,255,0.03); color: var(--text-muted); border: 1px solid rgba(255,255,255,0.06);')}">
                ${pos.stage >= 1 ? '✓ TP 1' : 'TP 1'}<br><span style="font-size: 7.5px; font-weight: 600;">+₹500</span>
              </div>
              <div style="padding: 3px 1px; text-align: center; border-radius: 4px; font-size: 8px; font-weight: 800; font-family: 'JetBrains Mono', monospace; ${pos.stage >= 2 ? 'background: rgba(0, 255, 163, 0.2); color: #00FFA3; border: 1px solid rgba(0, 255, 163, 0.5);' : (pos.stage === 1 ? 'background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px dashed rgba(56, 189, 248, 0.5);' : 'background: rgba(255,255,255,0.03); color: var(--text-muted); border: 1px solid rgba(255,255,255,0.06);')}">
                ${pos.stage >= 2 ? '✓ TP 2' : 'TP 2'}<br><span style="font-size: 7.5px; font-weight: 600;">+₹1K</span>
              </div>
              <div style="padding: 3px 1px; text-align: center; border-radius: 4px; font-size: 8px; font-weight: 800; font-family: 'JetBrains Mono', monospace; ${pos.stage >= 3 ? 'background: rgba(0, 255, 163, 0.2); color: #00FFA3; border: 1px solid rgba(0, 255, 163, 0.5);' : (pos.stage === 2 ? 'background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px dashed rgba(56, 189, 248, 0.5);' : 'background: rgba(255,255,255,0.03); color: var(--text-muted); border: 1px solid rgba(255,255,255,0.06);')}">
                ${pos.stage >= 3 ? '✓ TP 3' : 'TP 3'}<br><span style="font-size: 7.5px; font-weight: 600;">+₹1.5K</span>
              </div>
              <div style="padding: 3px 1px; text-align: center; border-radius: 4px; font-size: 8px; font-weight: 800; font-family: 'JetBrains Mono', monospace; ${pos.stage >= 4 ? 'background: rgba(0, 255, 163, 0.2); color: #00FFA3; border: 1px solid rgba(0, 255, 163, 0.5);' : (pos.stage === 3 ? 'background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px dashed rgba(56, 189, 248, 0.5);' : 'background: rgba(255,255,255,0.03); color: var(--text-muted); border: 1px solid rgba(255,255,255,0.06);')}">
                ${pos.stage >= 4 ? '✓ TP 4' : 'TP 4'}<br><span style="font-size: 7.5px; font-weight: 600;">+₹2K</span>
              </div>
              <div style="padding: 3px 1px; text-align: center; border-radius: 4px; font-size: 8px; font-weight: 800; font-family: 'JetBrains Mono', monospace; ${pos.stage >= 5 ? 'background: rgba(0, 255, 163, 0.2); color: #00FFA3; border: 1px solid rgba(0, 255, 163, 0.5);' : (pos.stage === 4 ? 'background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px dashed rgba(56, 189, 248, 0.5);' : 'background: rgba(255,255,255,0.03); color: var(--text-muted); border: 1px solid rgba(255,255,255,0.06);')}">
                ${pos.stage >= 5 ? '✓ TP 5' : 'TP 5'}<br><span style="font-size: 7.5px; font-weight: 600;">+₹2.5K</span>
              </div>
              <div style="padding: 3px 1px; text-align: center; border-radius: 4px; font-size: 8px; font-weight: 800; font-family: 'JetBrains Mono', monospace; ${pos.stage >= 6 ? 'background: rgba(168, 85, 247, 0.25); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.6); box-shadow: 0 0 8px rgba(168, 85, 247, 0.3);' : 'background: rgba(255,255,255,0.03); color: var(--text-muted); border: 1px solid rgba(255,255,255,0.06);'}">
                🎯 TP 6<br><span style="font-size: 7.5px; font-weight: 600;">+₹3K TARGET</span>
              </div>
            </div>

            <!-- Milestone Progress Bar & Loss Cap -->
            <div>
              <div style="display: flex; justify-content: space-between; font-size: 9px; font-family: 'JetBrains Mono', monospace; margin-bottom: 2px;">
                <span style="color: #ff4560; font-weight: 700;">🛑 Cap: -₹1,500</span>
                <span style="color: #38bdf8; font-weight: 700;">${pos.gainPct !== undefined ? `${pos.gainPct >= 0 ? '+' : ''}${pos.gainPct}%` : '0%'}</span>
                <span style="color: #00FFA3; font-weight: 800;">${pos.stage >= 6 ? 'Target Achieved 🎯' : `Next Goal: ${progressPct}%`}</span>
              </div>
              <div style="position: relative; width: 100%; height: 5px; background: rgba(255,255,255,0.08); border-radius: 3px;">
                <div style="position: absolute; left: 0; width: ${progressPct}%; height: 100%; background: ${isWin ? '#00FFA3' : '#ff4560'}; border-radius: 3px;"></div>
              </div>
              <div style="margin-top: 6px; font-size: 8.5px; font-family: 'JetBrains Mono', monospace; display: flex; justify-content: space-between; color: var(--text-muted); background: rgba(0,0,0,0.25); padding: 3px 6px; border-radius: 4px;">
                <span>🎯 Ladder: 500 (300) ➔ 1K (700) ➔ 1.5K (1.15K) ➔ 2K ➔ 2.5K ➔ 3K</span>
                <span style="color: #00FFA3; font-weight: 700;">${pos.stageNote || 'Running'}</span>
              </div>
            </div>
          </div>
        `;
      }).join('');
    }

    // 7. Section E (Left): 14 Symbols Scorecard Table
    const scorecardTbody = document.getElementById('tm-scorecard-tbody');
    if (scorecardTbody && s.symbolStats) {
      const symbolsOrder = ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'SENSEX', 'RELIANCE', 'HDFCBANK', 'ICICIBANK', 'SBIN', 'INFY', 'TCS', 'TATAMOTORS', 'AXISBANK', 'LT', 'BAJFINANCE'];
      scorecardTbody.innerHTML = symbolsOrder.map(sym => {
        const stat = s.symbolStats[sym] || {};
        const curPrice = (s.livePrices && s.livePrices[sym]) ? s.livePrices[sym] : 0.0;
        const dayOpen = (s.dayOpenPrices && s.dayOpenPrices[sym]) ? s.dayOpenPrices[sym] : curPrice;
        const chgPct = (s.pricePctChanges && s.pricePctChanges[sym]) ? s.pricePctChanges[sym] : 0.0;
        const isUp = chgPct >= 0;
        const totalTrades = stat.totalTrades || 0;
        const netPnl = stat.netPnlInr || 0;
        const isPos = netPnl >= 0;

        return `
          <tr>
            <td style="font-weight: 800; color: #fff;">${sym}</td>
            <td class="num" style="text-align: right; color: var(--text-muted);">₹${Number(dayOpen).toLocaleString('en-IN', {minimumFractionDigits: 1, maximumFractionDigits: 2})}</td>
            <td class="num" style="text-align: right; color: #fff; font-weight: 700;">₹${Number(curPrice).toLocaleString('en-IN', {minimumFractionDigits: 1, maximumFractionDigits: 2})}</td>
            <td class="num" style="text-align: right; font-weight: 700; color: ${isUp ? '#00FFA3' : '#ff4560'};">
              ${isUp ? '+' : ''}${chgPct.toFixed(2)}%
            </td>
            <td style="text-align: center; font-size: 10px; font-family: 'JetBrains Mono', monospace;">
              ${totalTrades} (${stat.wins || 0}W / ${stat.losses || 0}L)
            </td>
            <td class="num" style="text-align: right; font-weight: 800; color: ${isPos ? '#00FFA3' : '#ff4560'};">
              ${isPos ? '+' : ''}₹${Number(netPnl).toLocaleString('en-IN', {minimumFractionDigits: 1, maximumFractionDigits: 1})}
            </td>
          </tr>
        `;
      }).join('');
    }

    // 8. Section E (Right): Historical Day Closed Trades Ledger
    const closedCountBadge = document.getElementById('tm-closed-count-badge');
    const closedTbody = document.getElementById('tm-closed-ledger-tbody');
    const closedList = s.closedLedger || [];
    if (closedCountBadge) closedCountBadge.textContent = `${closedList.length} Closed`;

    if (closedTbody) {
      if (closedList.length === 0) {
        closedTbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 24px;">Day replay in progress... trades will log live as SL, Profit Lock, or TP are touched!</td></tr>';
      } else {
        closedTbody.innerHTML = closedList.map(t => {
          const isWin = (t.netPnlInr || 0) >= 0;
          const exitReason = t.exitReason || 'TRAILING_RUNNER_EXIT';

          const reasonBadgeStyle = (exitReason === 'TP_6_EXIT')
            ? 'background: rgba(168, 85, 247, 0.25); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.6); box-shadow: 0 0 8px rgba(168, 85, 247, 0.3);'
            : (exitReason === 'TP_5_EXIT')
            ? 'background: rgba(0, 227, 150, 0.25); color: #00FFA3; border: 1px solid rgba(0, 227, 150, 0.6);'
            : (exitReason === 'TP_4_EXIT')
            ? 'background: rgba(0, 227, 150, 0.2); color: #00FFA3; border: 1px solid rgba(0, 227, 150, 0.5);'
            : (exitReason === 'TP_3_EXIT')
            ? 'background: rgba(56, 189, 248, 0.25); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.6);'
            : (exitReason === 'TP_2_EXIT')
            ? 'background: rgba(56, 189, 248, 0.2); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.5);'
            : (exitReason === 'TP_1_EXIT' || exitReason === 'BROKERAGE_SHIELDED_SCRATCH')
            ? 'background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.5);'
            : (exitReason === 'SMART_SL_EXIT')
            ? 'background: rgba(251, 191, 36, 0.2); color: #fbbf24; border: 1px solid rgba(251, 191, 36, 0.5);'
            : (exitReason === 'MAX_LOSS_CAP_HIT')
            ? 'background: rgba(255, 69, 96, 0.25); color: #ff4560; border: 1px solid rgba(255, 69, 96, 0.6); box-shadow: 0 0 8px rgba(255, 69, 96, 0.3);'
            : (exitReason === 'DAILY_CIRCUIT_BREAKER_HIT')
            ? 'background: rgba(239, 68, 68, 0.25); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.6);'
            : (exitReason === 'INTRADAY_AUTO_SQUARE_OFF' || exitReason === '03:18_AUTO_SQUARE_OFF')
            ? 'background: rgba(168, 85, 247, 0.15); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.4);'
            : 'background: rgba(255, 69, 96, 0.15); color: #ff4560; border: 1px solid rgba(255, 69, 96, 0.4);';

          const reasonLabel = t.exitBadgeLabel || (
            (exitReason === 'TP_6_EXIT') ? '🎯 TP 6 (+₹3,000 TARGET)'
            : (exitReason === 'TP_5_EXIT') ? '🎯 TP 5 (+₹2,500 / LOCK 2.1K)'
            : (exitReason === 'TP_4_EXIT') ? '🎯 TP 4 (+₹2,000 / LOCK 1.6K)'
            : (exitReason === 'TP_3_EXIT') ? '🎯 TP 3 (+₹1,500 / LOCK 1.15K)'
            : (exitReason === 'TP_2_EXIT') ? '🎯 TP 2 (+₹1,000 / LOCK 700)'
            : (exitReason === 'TP_1_EXIT') ? '🎯 TP 1 (+₹500 / LOCK 300)'
            : (exitReason === 'SMART_SL_EXIT') ? `🛡️ SMART SL EXIT (-₹${Math.abs(t.netPnlInr || 0).toFixed(0)})`
            : (exitReason === 'MAX_LOSS_CAP_HIT') ? '🛑 MAX LOSS CAP (-₹1,500)'
            : (exitReason === 'DAILY_CIRCUIT_BREAKER_HIT') ? '🛡️ DAILY CIRCUIT BREAKER'
            : (exitReason === 'INTRADAY_AUTO_SQUARE_OFF' || exitReason === '03:18_AUTO_SQUARE_OFF') ? '⏰ 03:18 PM AUTO SQUARE-OFF'
            : '🛑 STOP LOSS HIT'
          );

          const actionStr = t.side || 'BUY';
          const actionColor = actionStr === 'BUY' ? 'var(--bull-green)' : 'var(--bear-red)';
          const timeStr = t.exitTimeFormatted || t.entryTimeFormatted || '';

          return `
            <tr>
              <td style="font-size: 10px; color: var(--text-secondary);">${timeStr}</td>
              <td style="font-weight: 800; color: #fff;">
                ${t.symbol} ${t.isOption ? `<span style="font-size: 9px; color: #fbbf24;">${t.optionType} ${t.optionStrike || ''}</span>` : ''}
              </td>
              <td style="color: ${actionColor}; font-weight: 700; font-size: 10px;">${actionStr}</td>
              <td class="num" style="text-align: right; font-size: 10px;">
                ₹${Number(t.entryPrice).toFixed(1)} → ₹${Number(t.exitPrice).toFixed(1)}
              </td>
              <td class="num" style="text-align: right; font-weight: 800; color: ${isWin ? '#00FFA3' : '#ff4560'};">
                ${isWin ? '+' : ''}₹${Number(t.netPnlInr || 0).toLocaleString('en-IN', {minimumFractionDigits: 1, maximumFractionDigits: 1})}
              </td>
              <td style="text-align: right;">
                <span style="font-size: 8.5px; font-weight: 700; padding: 2px 6px; border-radius: 4px; text-transform: uppercase; ${reasonBadgeStyle}">
                  ${reasonLabel}
                </span>
              </td>
            </tr>
          `;
        }).join('');
      }
    }
  }

  renderHeatmap() {
    const container = document.getElementById('heatmap-grid');
    if (!container) return;

    const items = Object.values(this.quotes).filter(x => x.type === 'equity');
    container.innerHTML = items.map(s => {
      const isUp = s.change >= 0;
      const intensity = Math.min(Math.abs(s.change_pct) / 3.0, 1.0);
      const bg = isUp ? `rgba(0, 227, 150, ${0.15 + intensity * 0.35})` : `rgba(255, 69, 96, ${0.15 + intensity * 0.35})`;

      return `
        <div style="background: ${bg}; border: 1px solid var(--border-subtle); border-radius: 4px; padding: 8px; cursor: pointer;"
             onclick="window.terminal.selectSymbol('${s.symbol}')">
          <div style="font-weight: 800; font-size: 11px;">${s.clean_symbol}</div>
          <div class="num" style="font-size: 12px; font-weight: 700; color: ${isUp ? 'var(--bull-green)' : 'var(--bear-red)'}">
            ${isUp ? '+' : ''}${s.change_pct.toFixed(2)}%
          </div>
          <div class="num" style="font-size: 10px; color: var(--text-muted);">₹${s.ltp.toFixed(2)}</div>
        </div>
      `;
    }).join('');
  }

  showToast(msg, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `<span>${msg}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      toast.style.transition = 'all 0.2s';
      setTimeout(() => toast.remove(), 250);
    }, 3200);
  }
}

// Bootstrap on DOM ready
document.addEventListener('DOMContentLoaded', () => {
  window.terminal = new NexusTerminalApp();
});
