/* Shared daily analysis archive and accessible dashboard navigation. */
(function () {
  'use strict';
  const el=id=>document.getElementById(id);
  const date=value=>typeof value==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(value)&&Number.isFinite(Date.parse(value))&&new Date(value).toISOString().slice(0,10)===value;
  const views=['explorer','rates','korea','us','etf','overseas-etf'];
  let entries=[], loading=false, failed=false, activeView='explorer', lastLoaded=0;
  function view(name) {
    activeView=views.includes(name)?name:'explorer';
    views.forEach(name=>{const panel=el(name+'-panel');if(panel)panel.hidden=name!==activeView;});
    document.querySelectorAll('[data-view]').forEach(button=>{const selected=button.dataset.view===activeView;button.setAttribute('aria-selected',String(selected));button.tabIndex=selected?0:-1;});
    if(activeView==='explorer'&&typeof window.requestAnimationFrame==='function')window.requestAnimationFrame(()=>{if(typeof chart!=='undefined'&&chart&&typeof chart.resize==='function')chart.resize();});
  }
  function route() {
    const parts=window.location.hash.slice(1).split('/');
    if(parts[0]==='briefing'||parts[0]==='heatmap') {
      const target=parts[0]==='briefing'&&parts[1]==='KR'?'korea':'us',hash='#'+target+(parts[0]==='briefing'&&date(parts[2])?'/'+parts[2]:'');
      // Replace the obsolete route so browser Back does not loop through it.
      if(window.history?.replaceState)window.history.replaceState(null,'',hash);else window.location.hash=hash;
      view(target);
      if(typeof window.dispatchEvent==='function'&&typeof window.Event==='function')window.dispatchEvent(new window.Event('hashchange'));
      return;
    }
    view(parts[0]);
    if(activeView==='korea'&&Date.now()-lastLoaded>=60000)load();
  }
  function navigate(name){const hash='#'+(views.includes(name)?name:'explorer');if(window.location.hash===hash)route();else window.location.hash=hash;}
  async function load(){
    if(loading)return;loading=true;const previous=JSON.stringify(entries),hadFailure=failed;failed=false;
    try{const response=await fetch('./data/briefings.json?ts='+Date.now(),{cache:'no-store'});if(!response.ok)throw Error('HTTP '+response.status);const payload=await response.json();if(payload.schemaVersion!==1||!Array.isArray(payload.entries))throw Error('Unsupported analysis archive schema');entries=payload.entries.filter(entry=>entry&&['US','KR'].includes(entry.market)&&date(entry.date));lastLoaded=Date.now();}
    catch(error){failed=true;console.error('Analysis archive:',error);}
    loading=false;window.TerminalBriefingData={entries:entries.slice(),failed};
    if((previous!==JSON.stringify(entries)||failed||hadFailure)&&typeof window.dispatchEvent==='function'&&typeof window.CustomEvent==='function')window.dispatchEvent(new window.CustomEvent('terminal-briefing-ready'));
  }
  function refresh(){if(document.visibilityState==='hidden'||activeView!=='korea'||Date.now()-lastLoaded<60000)return;load();}
  function boot(){
    const tabs=[...document.querySelectorAll('[data-view]')];
    tabs.forEach((button,index)=>{button.onclick=()=>navigate(button.dataset.view);button.onkeydown=event=>{let target=null;if(event.key==='ArrowRight')target=tabs[(index+1)%tabs.length];if(event.key==='ArrowLeft')target=tabs[(index+tabs.length-1)%tabs.length];if(event.key==='Home')target=tabs[0];if(event.key==='End')target=tabs[tabs.length-1];if(target){event.preventDefault();target.focus();navigate(target.dataset.view);}};});
    window.TerminalRefreshArchive=load;
    window.addEventListener('hashchange',route);window.addEventListener('focus',refresh);document.addEventListener('visibilitychange',refresh);
    if(typeof window.setInterval==='function')window.setInterval(refresh,300000);
    route();load();
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
}());
