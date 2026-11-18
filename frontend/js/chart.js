/**
 * NEXUS BHARAT - TradingView Lightweight Charts Orchestrator
 * High-performance 60fps Canvas Candlestick, Indicator Visualization & Sniper Overlay
 */

class NexusChartManager {
  constructor(mainContainerId, rsiContainerId) {
    this.mainContainer = document.getElementById(mainContainerId);
    this.rsiContainer = document.getElementById(rsiContainerId);

    this.chart = null;
    this.rsiChart = null;

    this.candleSeries = null;
    this.volumeSeries = null;
    this.ema20Series = null;
    this.ema50Series = null;
    this.vwapSeries = null;
    this.rsiSeries = null;

    // Sniper Price Lines
    this.sniperPriceLines = [];

    this.activeIndicators = {
      ema20: true,
      ema50: true,
      vwap: false,
      volume: true,
      rsi: true
    };

    this.currentData = null;

    this.initCharts();
    this.bindResize();
  }

  initCharts() {
    if (!window.LightweightCharts) {
      console.error("[NexusChart] LightweightCharts library not found!");
      return;
    }

    const chartOptions = {
      layout: {
        background: { color: '#090a0f' },
        textColor: '#94a3b8',
        fontSize: 11,
        fontFamily: "'JetBrains Mono', monospace"
      },
      grid: {
        vertLines: { color: 'rgba(255, 255, 255, 0.03)' },
        horzLines: { color: 'rgba(255, 255, 255, 0.03)' }
      },
      crosshair: {
        mode: window.LightweightCharts.CrosshairMode.Normal,
        vertLine: {
          color: '#38bdf8',
          width: 1,
          style: window.LightweightCharts.LineStyle.Dashed,
          labelBackgroundColor: '#1e293b'
        },
        horzLine: {
          color: '#38bdf8',
          width: 1,
          style: window.LightweightCharts.LineStyle.Dashed,
          labelBackgroundColor: '#1e293b'
        }
      },
      rightPriceScale: {
        borderColor: '#1f2636',
        scaleMargins: { top: 0.1, bottom: 0.2 },
        autoScale: true
      },
      timeScale: {
        borderColor: '#1f2636',
        timeVisible: true,
        secondsVisible: false
      }
    };

    // 1. Main Candlestick Chart
    this.chart = window.LightweightCharts.createChart(this.mainContainer, {
      ...chartOptions,
      width: this.mainContainer.clientWidth,
      height: this.mainContainer.clientHeight || 450
    });

    this.candleSeries = this.chart.addCandlestickSeries({
      upColor: '#00e396',
      downColor: '#ff4560',
      borderVisible: false,
      wickUpColor: '#00e396',
      wickDownColor: '#ff4560'
    });

    // Volume Overlay (Bottom 20% of main chart)
    this.volumeSeries = this.chart.addHistogramSeries({
      color: '#38bdf8',
      priceFormat: { type: 'volume' },
      priceScaleId: '',
      scaleMargins: { top: 0.8, bottom: 0 }
    });

    // EMA Overlays
    this.ema20Series = this.chart.addLineSeries({
      color: '#38bdf8', // Cyan
      lineWidth: 2,
      title: 'EMA 20',
      priceScaleId: 'right'
    });

    this.ema50Series = this.chart.addLineSeries({
      color: '#f59e0b', // Amber
      lineWidth: 2,
      title: 'EMA 50',
      priceScaleId: 'right'
    });

    this.vwapSeries = this.chart.addLineSeries({
      color: '#c084fc', // Purple
      lineWidth: 2,
      title: 'VWAP',
      priceScaleId: 'right'
    });

    // 2. RSI Sub-Chart
    const rsiOptions = {
      ...chartOptions,
      width: this.rsiContainer.clientWidth,
      height: this.rsiContainer.clientHeight || 110,
      rightPriceScale: {
        borderColor: '#1f2636',
        scaleMargins: { top: 0.1, bottom: 0.1 }
      },
      timeScale: {
        borderColor: '#1f2636',
        visible: false
      }
    };

    this.rsiChart = window.LightweightCharts.createChart(this.rsiContainer, rsiOptions);

    this.rsiSeries = this.rsiChart.addLineSeries({
      color: '#a855f7',
      lineWidth: 2,
      title: 'RSI 14'
    });

    // Add 70 and 30 reference lines
    this.rsiSeries.createPriceLine({
      price: 70,
      color: 'rgba(255, 69, 96, 0.6)',
      lineWidth: 1,
      lineStyle: window.LightweightCharts.LineStyle.Dotted,
      axisLabelVisible: true,
      title: '70 OVERBOUGHT'
    });
    this.rsiSeries.createPriceLine({
      price: 30,
      color: 'rgba(0, 227, 150, 0.6)',
      lineWidth: 1,
      lineStyle: window.LightweightCharts.LineStyle.Dotted,
      axisLabelVisible: true,
      title: '30 OVERSOLD'
    });

    this.chart.subscribeCrosshairMove((param) => {
      this.updateLegend(param);
    });
  }

  updateLegend(param) {
    if (!param || !param.time || !param.seriesData) return;

    const data = param.seriesData.get(this.candleSeries);
    if (!data) return;

    const elTime = document.getElementById('leg-time');
    const elO = document.getElementById('leg-open');
    const elH = document.getElementById('leg-high');
    const elL = document.getElementById('leg-low');
    const elC = document.getElementById('leg-close');
    const elV = document.getElementById('leg-vol');

    if (elO) elO.textContent = `₹${data.open.toFixed(2)}`;
    if (elH) elH.textContent = `₹${data.high.toFixed(2)}`;
    if (elL) elL.textContent = `₹${data.low.toFixed(2)}`;
    if (elC) {
      elC.textContent = `₹${data.close.toFixed(2)}`;
      elC.className = `c-val ${data.close >= data.open ? 'up' : 'down'}`;
    }

    const volData = param.seriesData.get(this.volumeSeries);
    if (elV && volData) {
      elV.textContent = volData.value.toLocaleString();
    }
  }

  renderData(apiData) {
    if (!apiData || !apiData.candles || apiData.candles.length === 0) return;
    this.currentData = apiData;

    const candleData = [];
    const volumeData = [];
    const ema20Data = [];
    const ema50Data = [];
    const vwapData = [];

    apiData.candles.forEach(c => {
      candleData.push({
        time: c.time,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close
      });

      volumeData.push({
        time: c.time,
        value: c.volume,
        color: c.close >= c.open ? 'rgba(0, 227, 150, 0.35)' : 'rgba(255, 69, 96, 0.35)'
      });

      if (c.ema20 !== null) ema20Data.push({ time: c.time, value: c.ema20 });
      if (c.ema50 !== null) ema50Data.push({ time: c.time, value: c.ema50 });
      if (c.vwap !== null) vwapData.push({ time: c.time, value: c.vwap });
    });

    this.candleSeries.setData(candleData);
    this.volumeSeries.setData(volumeData);
    this.ema20Series.setData(ema20Data);
    this.ema50Series.setData(ema50Data);
    this.vwapSeries.setData(vwapData);

    this.ema20Series.applyOptions({ visible: this.activeIndicators.ema20 });
    this.ema50Series.applyOptions({ visible: this.activeIndicators.ema50 });
    this.vwapSeries.applyOptions({ visible: this.activeIndicators.vwap });
    this.volumeSeries.applyOptions({ visible: this.activeIndicators.volume });

    if (apiData.rsi && apiData.rsi.length > 0) {
      const rsiData = apiData.rsi.map(r => ({ time: r.time, value: r.value }));
      this.rsiSeries.setData(rsiData);
    }

    this.chart.timeScale().fitContent();
    this.rsiChart.timeScale().fitContent();

    const last = apiData.candles[apiData.candles.length - 1];
    if (last) {
      document.getElementById('leg-open').textContent = `₹${last.open.toFixed(2)}`;
      document.getElementById('leg-high').textContent = `₹${last.high.toFixed(2)}`;
      document.getElementById('leg-low').textContent = `₹${last.low.toFixed(2)}`;
      document.getElementById('leg-close').textContent = `₹${last.close.toFixed(2)}`;
      document.getElementById('leg-vol').textContent = last.volume.toLocaleString();
    }
  }

  // =========================================================================
  // SNIPER PRICE LINES OVERLAY (PRE-REVERSAL TP, TIGHT SL, REVERSAL WALL)
  // =========================================================================
  clearSniperLevels() {
    if (!this.candleSeries) return;
    this.sniperPriceLines.forEach(line => {
      try {
        this.candleSeries.removePriceLine(line);
      } catch (e) {}
    });
    this.sniperPriceLines = [];
  }

  setSniperLevels(levels) {
    if (!this.candleSeries || !levels) return;
    this.clearSniperLevels();

    // 1. Entry Line
    if (levels.entryPrice) {
      const line = this.candleSeries.createPriceLine({
        price: levels.entryPrice,
        color: '#38bdf8',
        lineWidth: 1,
        lineStyle: window.LightweightCharts.LineStyle.Dashed,
        axisLabelVisible: true,
        title: 'SNIPER ENTRY'
      });
      this.sniperPriceLines.push(line);
    }

    // 2. Tight Structural SL (Red)
    if (levels.slPrice) {
      const line = this.candleSeries.createPriceLine({
        price: levels.slPrice,
        color: '#ff4560',
        lineWidth: 2,
        lineStyle: window.LightweightCharts.LineStyle.Solid,
        axisLabelVisible: true,
        title: `TIGHT SL (₹${levels.slPrice})`
      });
      this.sniperPriceLines.push(line);
    }

    // 3. Smart Pre-Reversal TP (Emerald Green)
    if (levels.tpPrice) {
      const line = this.candleSeries.createPriceLine({
        price: levels.tpPrice,
        color: '#00e396',
        lineWidth: 2,
        lineStyle: window.LightweightCharts.LineStyle.Solid,
        axisLabelVisible: true,
        title: `PRE-REVERSAL TP (₹${levels.tpPrice})`
      });
      this.sniperPriceLines.push(line);
    }

    // 4. First Reversal Wall (Amber/Orange)
    if (levels.firstReversalWallPrice) {
      const line = this.candleSeries.createPriceLine({
        price: levels.firstReversalWallPrice,
        color: '#f59e0b',
        lineWidth: 1,
        lineStyle: window.LightweightCharts.LineStyle.Dotted,
        axisLabelVisible: true,
        title: `REVERSAL WALL [${levels.reversalWallSource || 'SUPPLY'}]`
      });
      this.sniperPriceLines.push(line);
    }
  }

  toggleIndicator(indicatorName) {
    if (indicatorName in this.activeIndicators) {
      this.activeIndicators[indicatorName] = !this.activeIndicators[indicatorName];
      
      if (indicatorName === 'ema20') this.ema20Series.applyOptions({ visible: this.activeIndicators.ema20 });
      if (indicatorName === 'ema50') this.ema50Series.applyOptions({ visible: this.activeIndicators.ema50 });
      if (indicatorName === 'vwap') this.vwapSeries.applyOptions({ visible: this.activeIndicators.vwap });
      if (indicatorName === 'volume') this.volumeSeries.applyOptions({ visible: this.activeIndicators.volume });
      if (indicatorName === 'rsi') {
        this.rsiContainer.style.display = this.activeIndicators.rsi ? 'block' : 'none';
        this.resize();
      }
      return this.activeIndicators[indicatorName];
    }
    return false;
  }

  resize() {
    if (this.chart && this.mainContainer) {
      this.chart.applyOptions({
        width: this.mainContainer.clientWidth,
        height: this.mainContainer.clientHeight
      });
    }
    if (this.rsiChart && this.rsiContainer) {
      this.rsiChart.applyOptions({
        width: this.rsiContainer.clientWidth,
        height: this.rsiContainer.clientHeight
      });
    }
  }

  bindResize() {
    window.addEventListener('resize', () => {
      this.resize();
    });

    const observer = new ResizeObserver(() => {
      this.resize();
    });
    if (this.mainContainer) observer.observe(this.mainContainer);
  }
}

window.NexusChartManager = NexusChartManager;
