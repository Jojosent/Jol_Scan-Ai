/* Жалпы интерфейс, API, карта және статистика. Бөгде мәтін HTML ретінде енгізілмейді. */
'use strict';
window.Jol = (() => {
  const catalog = JSON.parse(document.getElementById('locale-catalog').textContent);
  const tr = (message, values = {}) => (catalog[message] || message || '')
    .replace(/\{(\w+)\}/g, (match, key) => values[key] ?? match);
  const locale = {kk:'kk-KZ', ru:'ru-RU', en:'en-GB'}[document.documentElement.lang];
  const severity = {HIGH:tr('Жоғары'), MEDIUM:tr('Орташа'), LOW:tr('Төмен'), NONE:tr('Ақау жоқ')};
  const statuses = {new:tr('Жаңа'), in_progress:tr('Жөнделуде'), repaired:tr('Жөнделді')};
  const colors = {HIGH:'#ef6464', MEDIUM:'#e8ac49', LOW:'#4bbb85', NONE:'#8092a5'};
  const $ = id => document.getElementById(id);
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let toastTimer;
  function toast(message, error=false) {
    const node=$('toast'); node.textContent=tr(message); node.className=`toast show${error?' error':''}`;
    clearTimeout(toastTimer); toastTimer=setTimeout(()=>node.classList.remove('show'),error?10000:5000);
  }
  async function api(url, options={}) {
    const headers = {'X-CSRF-Token':document.querySelector('meta[name="csrf-token"]').content,...options.headers};
    if(options.body && !(options.body instanceof FormData)) {headers['Content-Type']='application/json'; options.body=JSON.stringify(options.body);}
    let response;
    try { response=await fetch(url,{...options,headers,credentials:'same-origin'}); }
    catch { throw new Error(tr('Серверге қосылу мүмкін болмады. Интернет пен серверді тексеріңіз.')); }
    const data=await response.json().catch(()=>({error:tr('Сервер жауабы оқылмады. Қайта көріңіз.')}));
    if(!response.ok) throw new Error(tr(data.error)||tr('Сұрау орындалмады.'));
    return data;
  }
  function badge(level) {return `<span class="severity-badge severity-${escape(level)}">${escape(severity[level]||level)}</span>`;}
  function statusBadge(status) {return `<span class="status-badge ${escape(status)}">${escape(statuses[status]||status)}</span>`;}
  function date(value, short=false) {
    return new Intl.DateTimeFormat(locale,{timeZone:'Asia/Qyzylorda',day:'2-digit',month:short?'short':'2-digit',...(short?{}:{year:'numeric'})}).format(new Date(value));
  }
  async function loadStats() {
    const data=await api('/api/stats');
    document.querySelectorAll('[data-stat]').forEach(el=>{
      const target=Number(data[el.dataset.stat]||0);
      if(el.classList.contains('stat-number') && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
        const start=performance.now();
        function tick(now){const p=Math.min((now-start)/800,1);el.textContent=Math.round(target*(1-(1-p)**3)).toLocaleString(locale);if(p<1)requestAnimationFrame(tick);}
        requestAnimationFrame(tick);
      } else el.textContent=target.toLocaleString(locale);
    });
    if($('demo-note')) $('demo-note').hidden=!data.demo;
    return data;
  }
  function makeMap(id, options={}) {
    const container=$(id);
    if(!window.L) {container.textContent=tr('Карта кітапханасы жүктелмеді. Интернетті тексеріңіз.');return null;}
    container.textContent='';
    const map=L.map(id,{zoomControl:true,scrollWheelZoom:false,...options}).setView([51.145,71.435],11);
    const attribution = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';
    const dark = document.documentElement.dataset.theme === 'dark';
    const key = document.querySelector('meta[name="carto-basemap-key"]')?.content;
    function addOsm() {
      const tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution, maxZoom:19, className:dark ? 'osm-dark-fallback' : '',
      }).addTo(map);
      let errors = 0;
      tiles.on('tileerror', () => {
        if (++errors !== 5) return;
        const note = document.createElement('div');
        note.className = 'tile-error-note';
        note.textContent = tr('Карта қабаты жүктелмеді. Интернетті тексеріңіз; өтінім нүктелері қолжетімді.');
        container.append(note);
      });
    }
    if (dark && key) {
      const tiles = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png?key=' + encodeURIComponent(key), {
        attribution: attribution + ' · &copy; <a href="https://carto.com/attribution/">CARTO</a>',
        subdomains:'abcd', maxZoom:19,
      }).addTo(map);
      tiles.once('tileerror', () => { map.removeLayer(tiles); addOsm(); });
    } else {
      addOsm();
    }
    return map;
  }
  function popup(report) {
    const photo = report.annotated_url
      ? `<img class="popup-image" src="${escape(report.annotated_url)}" alt="${escape(tr('Ақау суреті'))}" loading="lazy">`
      : '';
    const details = report.created_at ? `${escape(date(report.created_at))} · ` : '';
    return `${photo}<strong class="popup-title">${escape(report.address||tr(report.district))}</strong>${badge(report.severity)} ${report.is_demo?`<span class="demo-badge">${escape(tr('ДЕМО'))}</span>`:''}<div class="popup-status">${statusBadge(report.status)}</div><div class="popup-meta">${details}#JS-${String(report.id).padStart(4,'0')}</div>`;
  }
  function addMarkers(map, reports) {
    if(!map) return null;
    const group=L.layerGroup().addTo(map);
    reports.filter(r=>Number.isFinite(r.latitude)&&Number.isFinite(r.longitude)).forEach(r=>{
      const marker = L.marker([r.latitude,r.longitude], {
        icon: L.divIcon({className:'defect-pin', iconSize:[20,20], iconAnchor:[10,10],
          html:`<span class="defect-dot" style="--pin-color:${colors[r.severity] || colors.NONE}"></span>`}),
        keyboard:Boolean(r.id), interactive:Boolean(r.id), title:severity[r.severity],
      }).addTo(group);
      if(r.id) marker.bindPopup(popup(r),{maxWidth:260});
    });
    return group;
  }
  function params() {
    const params=new URLSearchParams();
    ['severity','status','district','from','to'].forEach(key=>{const val=$('filter-'+key)?.value;if(val)params.set(key,val);});
    return params.toString();
  }
  function bindFilters(callback) {
    document.querySelectorAll('.filters select,.filters input').forEach(el=>el.addEventListener('change',callback));
    $('reset-filters')?.addEventListener('click',()=>{document.querySelectorAll('.filters select,.filters input').forEach(el=>el.value='');callback();});
  }
  async function home() {
    const data=await api('/api/map');
    const map=makeMap('overview-map',{zoomControl:false,dragging:!window.L?.Browser?.mobile});
    addMarkers(map,data.reports);
  }
  async function mapPage() {
    const map=makeMap('full-map',{scrollWheelZoom:true});
    if(!map) return;
    const focus = L.control({position:'topright'});
    focus.onAdd = () => {
      const button = L.DomUtil.create('button', 'map-focus');
      button.type = 'button';
      button.textContent = tr('Астанаға оралу');
      L.DomEvent.disableClickPropagation(button);
      button.addEventListener('click', () => {
        const center = [51.1694, 71.4491];
        if (matchMedia('(prefers-reduced-motion: reduce)').matches) map.setView(center, 12);
        else map.flyTo(center, 12, {duration:1.2});
      });
      return button;
    };
    focus.addTo(map);
    let markerLayer,heatLayer,reports=[],mode='markers',version=0;
    function render() {
      if(markerLayer)map.removeLayer(markerLayer);if(heatLayer)map.removeLayer(heatLayer);
      if(mode==='markers')markerLayer=addMarkers(map,reports);
      else if(L.heatLayer)heatLayer=L.heatLayer(reports.map(r=>[r.latitude,r.longitude,({HIGH:1,MEDIUM:.55,LOW:.25,NONE:.08})[r.severity]]),{radius:28,blur:23,minOpacity:.3,gradient:{.25:'#41cc87',.55:'#ffc400',1:'#ef6464'}}).addTo(map);
      $('markers-mode').classList.toggle('selected',mode==='markers');$('heat-mode').classList.toggle('selected',mode==='heat');
    }
    async function refresh() {
      const current=++version;
      try{const data=await api('/api/map?'+params());if(current!==version)return;reports=data.reports;$('map-count').textContent=reports.length;render();}
      catch(error){toast(error.message,true);}
    }
    $('markers-mode').addEventListener('click',()=>{mode='markers';render();});
    $('heat-mode').addEventListener('click',()=>{if(!L.heatLayer){toast(tr('Жылу картасы жүктелмеді. Интернетті тексеріңіз.'),true);return;}mode='heat';render();});
    bindFilters(refresh);await refresh();
    document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
    const selected=Number(new URLSearchParams(location.search).get('report'));
    if(selected){const report=reports.find(r=>r.id===selected);if(report){map.setView([report.latitude,report.longitude],15);L.popup().setLatLng([report.latitude,report.longitude]).setContent(popup(report)).openOn(map);}}
  }
  async function dashboard(stats) {
    if(!window.Chart){toast(tr('Графиктер жүктелмеді. Интернетті тексеріңіз.'),true);return;}
    Chart.defaults.color=getComputedStyle(document.documentElement).getPropertyValue('--muted').trim();Chart.defaults.font.family='Inter, JolSans, Arial, sans-serif';Chart.defaults.font.size=10;
    const scales={x:{grid:{color:'#252d37'},border:{display:false}},y:{beginAtZero:true,ticks:{precision:0},grid:{color:'#252d37'},border:{display:false}}};
    new Chart($('severity-chart'),{type:'doughnut',data:{labels:[tr('Төмен'),tr('Орташа'),tr('Жоғары'),tr('Ақау жоқ')],datasets:[{data:['LOW','MEDIUM','HIGH','NONE'].map(k=>stats.severity[k]),backgroundColor:['#4bbb85','#e8ac49','#ef6464','#627386'],borderWidth:5,borderColor:'#171a21',hoverOffset:6}]},options:{responsive:true,maintainAspectRatio:false,cutout:'75%',plugins:{legend:{position:'bottom',labels:{usePointStyle:true,pointStyle:'circle',padding:15,boxWidth:6}}}}});
    new Chart($('daily-chart'),{type:'line',data:{labels:stats.days.map(d=>d.date.slice(5).replace('-','.')),datasets:[{label:tr('Өтінімдер'),data:stats.days.map(d=>d.count),borderColor:'#e2c157',backgroundColor:'#ffc40009',fill:true,tension:.4,borderWidth:2,pointRadius:3,pointBackgroundColor:'#e2c157',pointBorderWidth:0}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales}});
    const districts=['Есіл','Алматы','Сарыарқа','Байқоңыр','Нұра'];
    Object.keys(stats.districts).forEach(k=>{if(!districts.includes(k))districts.push(k);});
    new Chart($('district-chart'),{type:'bar',data:{labels:districts.map(district => tr(district)),datasets:[{label:tr('Өтінімдер'),data:districts.map(k=>stats.districts[k]||0),backgroundColor:['#e4c45f','#a8b29a','#8da6ad','#b7ab8c','#7a8b83'],borderRadius:5,maxBarThickness:35}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales}});
  }
  async function reportsPage() {
    let version=0;
    async function refresh() {
      const current=++version;const query=params();
      $('csv-export').href='/export/csv?'+query;$('pdf-export').href='/export/pdf?'+query;
      try {
        const {reports}=await api('/api/reports?'+query);if(current!==version)return;
        reports.sort((a,b)=>b.priority-a.priority);
        $('report-count').textContent=reports.length;$('report-total-label').textContent=tr('Барлығы {count} өтінім',{count:reports.length});
        $('reports-table').innerHTML=reports.map(r=>`<tr><td><a class="report-id" href="/map?report=${r.id}"><img src="${escape(r.annotated_url)}" alt="${escape(tr('Жол ақауы'))}" loading="lazy"><span><b>#JS-${String(r.id).padStart(4,'0')}</b> ${r.is_demo?`<span class="demo-badge">${escape(tr('ДЕМО'))}</span>`:''}<small>${escape(date(r.created_at))}</small></span></a></td><td><strong>${escape(tr(r.district))}</strong><small>${escape(r.address||`${r.latitude.toFixed(4)}, ${r.longitude.toFixed(4)}`)}</small></td><td>${badge(r.severity)}</td><td>${r.count}</td><td><b class="yellow">${r.priority.toFixed(1)}</b></td><td>${statusBadge(r.status)}</td><td>${r.status!=='repaired'?`<button class="button secondary small status-action" data-id="${r.id}" data-status="${r.status==='new'?'in_progress':'repaired'}">${r.status==='new'?'Жұмысқа алу':'Жөнделді'}</button>`:`<span class="green">${escape(tr('✓ Аяқталды'))}</span>`}</td></tr>`).join('')||`<tr><td colspan="7" class="empty-state">${escape(tr('Бұл сүзгі бойынша өтінім табылмады.'))}</td></tr>`;
      } catch(error){toast(error.message,true);}
    }
    $('reports-table').addEventListener('click',async event=>{
      const button=event.target.closest('.status-action');if(!button)return;button.disabled=true;
      try{await api(`/api/reports/${button.dataset.id}/status`,{method:'PATCH',body:{status:button.dataset.status}});toast(tr('Мәртебе жаңартылды.'));await refresh();await loadStats();}
      catch(error){toast(error.message,true);button.disabled=false;}
    });
    bindFilters(refresh);await refresh();
  }
  function adminActions() {
    $('clear-demo').addEventListener('click',async()=>{
      if(!confirm(tr('Демо өтінімдерді және олардың суреттерін өшіргіңіз келе ме?')))return;
      const button=$('clear-demo');button.disabled=true;
      try{const result=await api('/api/demo',{method:'DELETE'});toast(tr('{count} демо өтінім өшірілді.',{count:result.deleted}));await loadStats();}
      catch(error){toast(error.message,true);}finally{button.disabled=false;}
    });
  }
  document.addEventListener('DOMContentLoaded',async()=>{
    const dateParts=new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Qyzylorda',day:'numeric',month:'numeric',year:'numeric'}).formatToParts(new Date());
    const part=key=>dateParts.find(p=>p.type===key).value;
    const months=['қаңтар','ақпан','наурыз','сәуір','мамыр','маусым','шілде','тамыз','қыркүйек','қазан','қараша','желтоқсан'];
    $('today-date').textContent = locale === 'kk-KZ' ? `${part('day')} ${months[Number(part('month'))-1]} ${part('year')}` : new Intl.DateTimeFormat(locale,{timeZone:'Asia/Qyzylorda',dateStyle:'long'}).format(new Date());
    const toggle=$('menu-toggle'),sidebar=$('sidebar'),scrim=$('sidebar-scrim');
    function close(){sidebar.classList.remove('open');scrim.classList.remove('open');toggle.setAttribute('aria-expanded','false');}
    toggle.addEventListener('click',()=>{const open=!sidebar.classList.contains('open');sidebar.classList.toggle('open',open);scrim.classList.toggle('open',open);toggle.setAttribute('aria-expanded',String(open));});
    scrim.addEventListener('click',close);document.addEventListener('keydown',e=>{if(e.key==='Escape')close();});
    try {const stats=await loadStats();const page=document.body.dataset.page;
      if(page==='home')await home();if(page==='map')await mapPage();if(page==='dashboard')await dashboard(stats);if(page==='reports'){adminActions();await reportsPage();}
    }catch(error){toast(error.message,true);document.querySelectorAll('.skeleton').forEach(el=>{el.className='empty-state';el.textContent=tr('Деректер жүктелмеді. Бетті жаңартыңыз.');});}
  });
  return {$,api,toast,escape,badge,makeMap,loadStats,severity,tr};
})();
