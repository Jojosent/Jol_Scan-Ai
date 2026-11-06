/* Фото/видео кезегі, салыстыру жүгірткісі және координатты растау. */
'use strict';
document.addEventListener('DOMContentLoaded',()=>{
  const {$,api,toast,escape,badge,makeMap,loadStats,tr}=window.Jol;
  const {armSound,beep,demoResult,showPhotoOverlay,showEstimate,exportOrder}=window.JolShowcase;
  let files=[],results=[],current=0,map=null,marker=null,coordinates=null,busy=false,webcamStream=null;
  const positions=new Map();const addresses=new Map();const urls=[];
  const presets = [...document.querySelectorAll('[data-preset]')];
  const uploadLimit = Number($('file-input').dataset.limitMb);
  const isVideo = file => /\.(mp4|webm|mov)$/i.test(file.name);
  let previewUrl;

  async function fitUpload(file) {
    if (file.size <= uploadLimit * 1024 * 1024) return file;
    if (isVideo(file)) throw new Error(tr('Файл көлемі {mb} МБ-тан аспауы керек.', {mb:uploadLimit}));
    const image = await createImageBitmap(file);
    try {
      const canvas = document.createElement('canvas');
      const scale = Math.min(1, 1600 / Math.max(image.width, image.height));
      canvas.width = Math.max(1, Math.round(image.width * scale));
      canvas.height = Math.max(1, Math.round(image.height * scale));
      const drawing = canvas.getContext('2d');
      drawing.fillStyle = '#fff';
      drawing.fillRect(0, 0, canvas.width, canvas.height);
      drawing.drawImage(image, 0, 0, canvas.width, canvas.height);
      const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', .82));
      if (!blob || blob.size > uploadLimit * 1024 * 1024) {
        throw new Error(tr('Файл көлемі {mb} МБ-тан аспауы керек.', {mb:uploadLimit}));
      }
      return new File([blob], file.name.replace(/\.[^.]+$/, '.jpg'), {type:'image/jpeg'});
    } finally {
      image.close();
    }
  }

  function releasePreview() {
    $('scan-image').removeAttribute('src');
    const video = $('scan-video');
    if (video.hasAttribute('src')) {
      video.removeAttribute('src');
      video.load();
    }
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = null;
  }

  function showScan(source, message, {demo=false, video=false, frame=1}={}) {
    releasePreview();
    const image = $('scan-image');
    const clip = $('scan-video');
    image.hidden = video;
    clip.hidden = !video;
    (video ? clip : image).src = source;
    $('scan-mode').textContent = demo ? 'DEMO SCANNING…' : 'AI SCANNING…';
    $('scan-geo').textContent = demo ? 'SOURCE: PHOTO' : 'GEO: —';
    $('scan-frame').textContent = demo ? 'FPS: 30' : 'FILE: ' + String(frame).padStart(2, '0');
    $('progress-text').textContent = message;
    const hud = $('analysis-progress');
    hud.hidden = false;
    hud.scrollIntoView({block:'center'});
  }

  function setBusy(value) {
    busy = value;
    presets.forEach(button => { button.disabled = value; });
    $('camera-button').disabled = value;
    renderQueue();
    if (!value) {
      $('analysis-progress').hidden = true;
      releasePreview();
    }
  }

  function revealResult(index) {
    $('analysis-progress').hidden = true;
    showResult(index);
    $('results-section').scrollIntoView({block:'start', behavior:matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'});
  }

  presets.forEach(button => button.addEventListener('click', async () => {
    if (busy) return;
    armSound();
    setBusy(true);
    try {
      const result = demoResult(button.dataset.preset);
      showScan(result.original_url, result.source, {demo:true});
      await new Promise(resolve => setTimeout(resolve, 1000));
      results.push(result);
      revealResult(results.length - 1);
      beep();
    } finally {
      setBusy(false);
    }
  }));
  function addFiles(incoming) {
    if(busy)return;
    for(const file of incoming){
      if(files.length>=8){toast(tr('Бір кезекте ең көбі 8 файл.'),true);break;}
      if(file.size>15*1024*1024){toast(`${file.name}: ${tr('файл көлемі 15 МБ-тан үлкен.')}`,true);continue;}
      if(!/\.(jpe?g|png|webp|mp4|mov|webm)$/i.test(file.name)){toast(`${file.name}: ${tr('бұл пішім қолдау таппайды.')}`,true);continue;}
      files.push(file);
    }
    renderQueue();$('file-input').value='';$('camera-input').value='';
  }
  function renderQueue(){
    urls.forEach(url=>URL.revokeObjectURL(url));urls.length=0;
    $('file-queue').innerHTML=files.map((file,index)=>{let thumbnail='';if(file.type.startsWith('image/')){const url=URL.createObjectURL(file);urls.push(url);thumbnail=`<img src="${url}" alt="${escape(tr('Таңдалған сурет'))}">`;}
      return `<div class="queue-item">${thumbnail}<span>${escape(file.name)}</span><small>${(file.size/1048576).toFixed(1)} ${tr('МБ')}</small><button class="icon-button" data-remove="${index}" aria-label="${escape(file.name)} ${escape(tr('файлын жою'))}" ${busy?'disabled':''}>×</button></div>`;}).join('');
    $('start-analysis').disabled=!files.length||busy;
  }
  $('file-input').addEventListener('change',e=>addFiles(e.target.files));$('camera-input').addEventListener('change',e=>addFiles(e.target.files));
  $('browse-button').addEventListener('click',e=>{e.stopPropagation();if(!busy)$('file-input').click();});
  $('dropzone').addEventListener('click',()=>{if(!busy)$('file-input').click();});
  $('dropzone').addEventListener('keydown',e=>{if((e.key==='Enter'||e.key===' ')&&e.target===$('dropzone')){e.preventDefault();if(!busy)$('file-input').click();}});
  $('camera-button').addEventListener('click',()=>{if(!busy)$('camera-input').click();});
  ['dragenter','dragover'].forEach(name=>$('dropzone').addEventListener(name,e=>{e.preventDefault();$('dropzone').classList.add('dragover');}));
  ['dragleave','drop'].forEach(name=>$('dropzone').addEventListener(name,e=>{e.preventDefault();$('dropzone').classList.remove('dragover');}));
  $('dropzone').addEventListener('drop',e=>addFiles(e.dataTransfer.files));
  $('file-queue').addEventListener('click',e=>{const button=e.target.closest('[data-remove]');if(button&&!busy){files.splice(Number(button.dataset.remove),1);renderQueue();}});
  $('start-analysis').addEventListener('click',async()=>{
    if(!files.length||busy)return;
    const step=Number($('frame-step').value);
    if(!Number.isInteger(step)||step<10||step>300){toast(tr('Кадр аралығы 10–300 болуы керек.'),true);return;}
    armSound();
    setBusy(true);
    let failures=0;const failedFiles=[];
    const startIndex = results.length;
    try {
      for(let i=0;i<files.length;i++){
        const url = URL.createObjectURL(files[i]);
        showScan(url, `${tr('Gemini талдауы:')} ${i+1} / ${files.length} ${tr('файл…')}`, {
          video:/\.(mp4|webm|mov)$/i.test(files[i].name), frame:i + 1,
        });
        previewUrl = url;
        try {
          const form = new FormData();
          form.append('file', await fitUpload(files[i]));
          form.append('frame_step', String(step));
          const data = await api('/api/detect',{method:'POST',body:form});
          data.results.forEach(result => { result.source=files[i].name; results.push(result); });
        }
        catch(error){failures++;failedFiles.push(files[i]);toast(`${files[i].name}: ${error.message}`,true);}
      }
      files=failedFiles;
      if(results.length > startIndex){revealResult(results.length-1);beep();}
      if(!failures)toast(tr('Талдау аяқталды. Орналасқан жерін көрсетіп, өтінімді сақтаңыз.'));
    } finally {setBusy(false);}
  });
  function setPosition(lat,lon,source){
    coordinates={latitude:lat,longitude:lon};const report=results[current];if(report)positions.set(report.token,coordinates);
    $('coordinates-label').textContent=`${lat.toFixed(6)}, ${lon.toFixed(6)}`;$('location-help').textContent=source||tr('Орны белгіленді. Қажет болса, маркерді жылжытыңыз.');
    if(map){if(!marker){marker=L.marker([lat,lon],{draggable:true}).addTo(map);marker.on('dragend',()=>{const pos=marker.getLatLng();setPosition(pos.lat,pos.lng);});}else marker.setLatLng([lat,lon]);map.panTo([lat,lon]);}
    $('save-report').disabled=Boolean(report?.saved || report?.demo);
  }
  function showResult(index){
    if(results[current])addresses.set(results[current].token,$('address').value);
    current=index;const report=results[index];
    $('result-tabs').innerHTML=results.map((r,i)=>`<button class="result-tab ${i===index?'active':''}" data-result="${i}" title="${escape(r.source)}">${i+1}. ${escape(r.demo ? r.source : r.frame_second!==null ? `${r.frame_second} ${tr('с кадр')}` : tr('Фото'))} ${r.saved?'✓':''}</button>`).join('');
    $('result-original').src=report.original_url;$('result-annotated').src=report.annotated_url;
    showPhotoOverlay(report);
    $('result-summary').textContent=report.count?report.summary:tr('Жақсы жаңалық! Жол ақаулары анықталмады.');
    $('result-recommendation').textContent=report.recommendation;
    $('result-metrics').innerHTML=[[tr('Ақаулар саны'),String(report.count)],[tr('Қауіп деңгейі'),badge(report.severity)],[tr('AI өзіндік бағасы'),report.demo||report.confidence===null?'—':`${Math.round(report.confidence*100)}%`],[tr('Талдау уақыты'),report.demo?'—':`${(report.inference_ms/1000).toFixed(1)} ${tr('с')}`]].map(([label,value])=>`<div class="result-metric"><small>${escape(label)}</small><strong>${value}</strong></div>`).join('');
    $('results-section').hidden=false;
    $('result-provider').textContent = report.demo ? tr('ДЕМО') : 'Gemini Vision';
    document.querySelector('.compare-label.after').textContent = tr(report.demo ? 'ДЕМО' : 'AI талдауы');
    $('location-panel').hidden = Boolean(report.demo);
    showEstimate(report);
    $('compare-range').value=50;updateComparison();
    if (report.demo) {
      coordinates = null;
      $('address').value = '';
      $('save-report').disabled = true;
      return;
    }
    if(!map){map=makeMap('location-map',{scrollWheelZoom:true});map?.on('click',e=>{if(!results[current].saved&&!results[current].demo)setPosition(e.latlng.lat,e.latlng.lng);});}
    coordinates=null;if(marker&&map){map.removeLayer(marker);marker=null;}
    $('address').value=addresses.get(report.token)||report.address||'';$('address').disabled=report.saved;
    $('save-report').textContent=report.saved?tr('✓ Өтінім сақталды'):tr('Өтінімді сақтау');$('save-report').disabled=true;
    const position=positions.get(report.token)||((report.latitude!==null&&report.longitude!==null)?{latitude:report.latitude,longitude:report.longitude}:null);
    if(position)setPosition(position.latitude,position.longitude,tr('Орналасқан жері анықталды. Картадан тексеріңіз.'));
    else{$('coordinates-label').textContent=tr('Координаттар таңдалмады');$('location-help').textContent=tr('Картадан ақаудың орнын белгілеңіз немесе геолокацияны қосыңыз.');map?.setView([51.145,71.435],11);}
    if(report.saved)marker?.dragging.disable();
    $('geolocate-button').disabled=report.saved;
    setTimeout(()=>map?.invalidateSize(),100);
  }
  $('result-tabs').addEventListener('click',e=>{const button=e.target.closest('[data-result]');if(button)showResult(Number(button.dataset.result));});
  function updateComparison(){const value=$('compare-range').value;$('comparison-after').style.clipPath=`inset(0 0 0 ${value}%)`;$('comparison-handle').style.left=value+'%';}
  $('compare-range').addEventListener('input',updateComparison);
  $('geolocate-button').addEventListener('click',()=>{
    if(!navigator.geolocation){toast(tr('Браузер геолокацияны қолдамайды. Картадан орынды таңдаңыз.'),true);return;}
    const token=results[current].token;$('geolocate-button').disabled=true;
    navigator.geolocation.getCurrentPosition(pos=>{if(results[current].token===token){setPosition(pos.coords.latitude,pos.coords.longitude,tr('Браузер геолокациясы, дәлдігі шамамен {accuracy} м. Орнын тексеріңіз.',{accuracy:Math.round(pos.coords.accuracy)}));map?.setZoom(15);}$('geolocate-button').disabled=results[current].saved;},()=>{$('geolocate-button').disabled=results[current].saved;toast(tr('Орныңыз анықталмады. HTTPS рұқсатын тексеріңіз немесе картадан таңдаңыз.'),true);},{enableHighAccuracy:true,timeout:12000,maximumAge:0});
  });
  $('save-report').addEventListener('click',async()=>{
    if(!coordinates||results[current].saved||results[current].demo)return;
    const index=current;const report=results[index];const button=$('save-report');button.disabled=true;
    try{const data=await api('/api/reports',{method:'POST',body:{token:report.token,...coordinates,address:$('address').value}});results[index]={...report,...data.report};toast(tr('Өтінім сақталды! Ол жол қызметіне жіберілді.'));if(current===index)showResult(index);await loadStats();}
    catch(error){toast(error.message,true);if(current===index)button.disabled=false;}
  });
  $('export-order').addEventListener('click', () => {
    const report = results[current];
    if (report) exportOrder(report, $('address').value, coordinates);
  });
  function stopWebcam(){webcamStream?.getTracks().forEach(track=>track.stop());webcamStream=null;$('webcam-video').srcObject=null;}
  $('webcam-button').addEventListener('click',async()=>{
    if(busy)return;
    if(!navigator.mediaDevices?.getUserMedia){toast(tr('Веб-камера үшін HTTPS немесе localhost қажет. Файл таңдау батырмасын қолданыңыз.'),true);return;}
    $('webcam-button').disabled=true;
    try{webcamStream=await navigator.mediaDevices.getUserMedia({video:{facingMode:{ideal:'environment'},width:{ideal:1280}},audio:false});$('webcam-video').srcObject=webcamStream;$('webcam-dialog').showModal();}
    catch{toast(tr('Камера ашылмады. Браузер рұқсатын тексеріңіз немесе файл таңдаңыз.'),true);stopWebcam();}
    finally{$('webcam-button').disabled=false;}
  });
  $('close-webcam').addEventListener('click',()=>$('webcam-dialog').close());
  $('webcam-dialog').addEventListener('close',stopWebcam);
  $('capture-webcam').addEventListener('click',()=>{
    const video=$('webcam-video');if(!video.videoWidth){toast(tr('Камера дайын болғанша күтіңіз.'),true);return;}
    const canvas=document.createElement('canvas');canvas.width=video.videoWidth;canvas.height=video.videoHeight;canvas.getContext('2d').drawImage(video,0,0);
    canvas.toBlob(blob=>{if(blob){addFiles([new File([blob],`camera-${Date.now()}.jpg`,{type:'image/jpeg'})]);$('webcam-dialog').close();}},'image/jpeg',.9);
  });
  window.addEventListener('beforeunload',()=>{urls.forEach(url=>URL.revokeObjectURL(url));releasePreview();stopWebcam();});
});
