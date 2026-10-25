/* Public-domain FRED images and official provider widgets. No copied ICE data. */
(function () {
  'use strict';
  const SERIES = new Set(['DGS10','HQMCB10YRP','DCOILWTICO','DCOILBRENTEU','DEXJPUS','DEXKOUS','DTWEXBGS']);
  const TRADINGVIEW_SCRIPT = 'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js';
  const MACRO_SYMBOLS = new Set(['OTCB:US10Y','FX:USOIL','FX:UKOIL','CAPITALCOM:DXY','FX:USDJPY','FX_IDC:USDKRW']);
  function loadMacroComponents() {
    document.querySelectorAll('[data-macro-chart]').forEach(holder => {
      if (holder.dataset.loaded || !MACRO_SYMBOLS.has(holder.dataset.macroChart)) return;
      const template = holder.querySelector('template');
      if (!template) return;
      const fragment = document.importNode(template.content, true);
      const original = fragment.querySelector('script');
      if (!original || original.getAttribute('src') !== TRADINGVIEW_SCRIPT) return;
      const script = document.createElement('script');
      script.type = original.type; script.src = TRADINGVIEW_SCRIPT; script.async = true;
      script.textContent = original.textContent;
      const container = original.parentNode; original.remove();
      script.onerror = () => {
        const status = holder.parentElement.querySelector('[data-macro-chart-status]');
        if (status) status.textContent = '외부 차트 연결 실패 · 아래 원본 링크에서 확인해 주세요.';
      };
      holder.dataset.loaded = 'true'; holder.append(fragment); container.append(script);
    });
  }
  function loadTradingView() {
    document.querySelectorAll('[data-tradingview-widget]').forEach(holder => {
      if (holder.dataset.loaded) return;
      const template = holder.querySelector('template');
      const status = holder.parentElement.querySelector('[data-tradingview-status]');
      if (!template) return;
      const fragment = document.importNode(template.content, true);
      const original = fragment.querySelector('script');
      // Only activate the official embed script from our reviewed, static templates.
      if (!original || original.getAttribute('src') !== TRADINGVIEW_SCRIPT) return;
      const container = original.parentNode;
      const script = document.createElement('script');
      script.type = original.type; script.src = TRADINGVIEW_SCRIPT; script.async = true;
      script.textContent = original.textContent;
      original.remove();
      holder.dataset.loaded = 'true';
      let observer;
      const labelFrame = () => {
        const frame = holder.querySelector('iframe');
        if (!frame) return;
        if (!frame.getAttribute('title')) frame.setAttribute('title', holder.getAttribute('aria-label'));
        if (observer) observer.disconnect();
      };
      if (typeof window.MutationObserver === 'function') {
        observer = new window.MutationObserver(labelFrame);
        observer.observe(holder, {childList:true, subtree:true});
      }
      script.onerror = () => {
        if (observer) observer.disconnect();
        if (status) status.textContent = 'TradingView 차트를 불러오지 못했습니다. 아래 원본 링크에서 확인하거나 페이지를 새로고침해 주세요.';
      };
      holder.append(fragment);
      // A fresh script node runs after its original provider container is attached.
      // Keep all generated settings and branding unchanged; do not read the iframe.
      container.append(script);
      labelFrame();
    });
  }
  function range(now = new Date()) {
    const end = now.toISOString().slice(0,10), start = new Date(end+'T00:00:00Z');
    const month = start.getUTCMonth(); start.setUTCFullYear(start.getUTCFullYear()-5);
    if (start.getUTCMonth() !== month) start.setUTCDate(0);
    return {start:start.toISOString().slice(0,10),end};
  }
  function imageUrl(series, dates, width) {
    if (!SERIES.has(series)) return '';
    const url = new URL('https://fred.stlouisfed.org/graph/fredgraph.png');
    Object.entries({id:series,cosd:dates.start,coed:dates.end,width:String(width || (['DEXKOUS','DTWEXBGS'].includes(series)?1100:1000)),height:'500'}).forEach(([key,value])=>url.searchParams.set(key,value));
    return url.href;
  }
  function load() {
    if (window.location.hash.split('/')[0] !== '#rates') return;
    loadTradingView();
    loadMacroComponents();
    const dates = range();
    document.querySelectorAll('[data-fred-series]').forEach(holder => {
      const series = holder.dataset.fredSeries;
      if (holder.dataset.loaded || !SERIES.has(series)) return;
      holder.dataset.loaded = 'true';
      const image = document.createElement('img');
      image.className = 'fred-image'; image.loading = 'lazy'; image.decoding = 'async';
      image.alt = `FRED ${series} 차트, ${dates.start}부터 ${dates.end}까지. 최신 관측일은 원본 참조.`;
      image.width = 1000; image.height = 500;
      const status = document.createElement('p'); status.className = 'fred-status';
      status.textContent = 'FRED 차트를 불러오는 중입니다. 표시되지 않으면 아래 원본을 열어 주세요.';
      image.onload = () => { status.textContent = `${dates.start} ~ ${dates.end} · 조회 구간이며 최신 관측일과 다를 수 있습니다.`; };
      image.onerror = () => { image.hidden = true; status.classList.add('fred-error'); status.textContent = 'FRED 차트를 불러오지 못했습니다. 아래 원본 링크에서 확인하거나 페이지를 새로고침해 주세요.'; };
      const retry = document.createElement('button'); retry.className = 'fred-retry'; retry.type = 'button'; retry.textContent = '차트 다시 불러오기';
      let alternate = false;
      retry.onclick = () => { alternate = !alternate; image.hidden = false; status.textContent = 'FRED 차트를 다시 불러오는 중입니다. 빈 화면이면 원본 링크를 이용하세요.'; image.src = imageUrl(series,range(),alternate?1200:1100); };
      holder.append(image,status,retry); image.src = imageUrl(series,dates);
    });
  }
  function boot() { window.addEventListener('hashchange',load); load(); }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
}());
