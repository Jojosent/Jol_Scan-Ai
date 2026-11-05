'use strict';

window.JolShowcase = (() => {
  const {tr, escape, $} = window.Jol;
  const locale = {kk:'kk-KZ', ru:'ru-RU', en:'en-GB'}[document.documentElement.lang];
  const decimal = new Intl.NumberFormat(locale, {maximumFractionDigits:2});
  const tenge = value => decimal.format(value) + ' ₸';
  const cases = {
    bridge: {title:'Көпірдегі ойық', severity:'HIGH', width:800, height:533, points:[[245,392],[284,364],[354,359],[475,328],[578,308],[619,321],[582,340],[467,363],[363,390],[286,404]]},
    crack: {title:'Жол жабынындағы жарық', severity:'MEDIUM', width:640, height:426, points:[[0,369],[53,328],[100,302],[129,278],[185,246],[226,225],[270,208],[331,191],[363,170],[393,158],[390,145],[438,123],[476,126],[530,90],[535,100],[491,135],[445,148],[423,145],[410,162],[372,182],[341,201],[291,218],[241,243],[205,258],[147,291],[117,322],[73,337],[25,372],[0,392]]},
    drain: {title:'Ашық су қабылдағыш', severity:'HIGH', width:740, height:986, points:[[218,498],[250,451],[279,430],[331,420],[384,429],[420,453],[452,475],[432,505],[375,516],[309,514],[258,506]]},
  };
  let audio;
  let soundEnabled = localStorage.getItem('jolscan-sound') !== 'off';
  const soundButton = $('scan-sound');

  function syncSound() {
    const label = tr(soundEnabled ? 'Дыбыс қосулы' : 'Дыбыс өшірулі');
    soundButton.setAttribute('aria-pressed', String(soundEnabled));
    soundButton.setAttribute('aria-label', label);
    soundButton.title = label;
    soundButton.querySelector('.sound-muted').hidden = soundEnabled;
  }

  function armSound() {
    const Audio = window.AudioContext || window.webkitAudioContext;
    if (!soundEnabled || !Audio) return;
    try {
      audio ??= new Audio();
      if (audio.state === 'suspended') audio.resume().catch(() => {});
    } catch { /* Sound is optional on browsers that block Web Audio. */ }
  }

  function beep() {
    if (!soundEnabled || audio?.state !== 'running') return;
    const now = audio.currentTime;
    const oscillator = audio.createOscillator();
    const gain = audio.createGain();
    oscillator.frequency.setValueAtTime(800, now);
    oscillator.frequency.setValueAtTime(1200, now + .06);
    gain.gain.setValueAtTime(.001, now);
    gain.gain.exponentialRampToValueAtTime(.10, now + .015);
    gain.gain.exponentialRampToValueAtTime(.001, now + .12);
    oscillator.connect(gain).connect(audio.destination);
    oscillator.start(now);
    oscillator.stop(now + .12);
    oscillator.onended = () => { oscillator.disconnect(); gain.disconnect(); };
  }

  soundButton.addEventListener('click', () => {
    soundEnabled = !soundEnabled;
    localStorage.setItem('jolscan-sound', soundEnabled ? 'on' : 'off');
    syncSound();
    if (soundEnabled) armSound();
  });
  syncSound();

  function demoResult(id) {
    const {title, severity, points, width, height} = cases[id];
    const polygon = points.map(([x,y]) => [x / width, y / height]);
    const areaRatio = Math.abs(polygon.reduce((sum, [x,y], index) => {
      const [nextX,nextY] = polygon[(index + 1) % polygon.length];
      return sum + x * nextY - y * nextX;
    }, 0)) / 2;
    const xs = polygon.map(([x]) => x * 1000);
    const ys = polygon.map(([,y]) => y * 1000);
    const original = '/static/img/presets/' + id;
    return {
      token:'preset-' + id, demo:true, saved:false, source:tr(title), severity, count:1,
      confidence:.94, inference_ms:null, frame_second:null, latitude:null, longitude:null,
      original_url:original + '.png', annotated_url:original + '.png',
      photoOverlay:{width,height,points},
      summary:tr(title), recommendation:tr('Бұл — дайын деректері бар оқу сценарийі.'),
      detections:[{label:tr(title), severity, confidence:.94, area_ratio:areaRatio,
        box:[Math.min(...ys), Math.min(...xs), Math.max(...ys), Math.max(...xs)],
        polygon:polygon.map(([x,y]) => [x * 1000, y * 1000])}],
    };
  }

  function showPhotoOverlay(report) {
    const overlay = $('comparison-overlay');
    overlay.replaceChildren();
    overlay.toggleAttribute('hidden', !report.photoOverlay);
    if (!report.photoOverlay) return;
    const {width,height,points} = report.photoOverlay;
    const svg = 'http://www.w3.org/2000/svg';
    const polygon = document.createElementNS(svg,'polygon');
    const color = report.severity === 'HIGH' ? '#f64b65' : '#ffb931';
    overlay.setAttribute('viewBox', `0 0 ${width} ${height}`);
    polygon.setAttribute('points', points.map(point => point.join(',')).join(' '));
    polygon.setAttribute('fill', color);
    polygon.setAttribute('fill-opacity', '.23');
    polygon.setAttribute('stroke', color);
    polygon.setAttribute('stroke-width', '3');
    polygon.setAttribute('vector-effect', 'non-scaling-stroke');
    overlay.append(polygon);
  }

  function estimate(report) {
    const ratio = report.detections.reduce((total, defect) => {
      const area = Number(defect.area_ratio);
      return total + (Number.isFinite(area) && area > 0 && area <= 1 ? area : 0);
    }, 0);
    const area = Math.round(Math.min(ratio, 1) * 450) / 100;
    const cost = Math.round(area * 14500);
    return {area, weight:area * 120, cost, deferred:cost * 6,
      risk:{HIGH:8.5, MEDIUM:5.5, LOW:2.5, NONE:1}[report.severity]};
  }

  function rows(report) {
    const values = estimate(report);
    return [
      [tr('Шамамен ауданы'), decimal.format(values.area) + ' m²'],
      [tr('Ыстық асфальт қоспасы'), decimal.format(values.weight) + ' kg'],
      [tr('Есептік жөндеу құны'), tenge(values.cost)],
      [tr('Шартты қауіп индексі'), decimal.format(values.risk) + ' / 10'],
      [tr('Кейінге қалдыру сценарийі (×6)'), tenge(values.deferred)],
      [tr('Модельдегі ықтимал үнем'), tenge(values.deferred - values.cost)],
    ];
  }

  const tableRows = report => rows(report)
    .map(([label, value]) => '<tr><th scope="row">' + escape(label) + '</th><td>' + escape(value) + '</td></tr>').join('');

  function showEstimate(report) {
    $('estimate-values').innerHTML = tableRows(report);
    $('estimate-risk').textContent = tr(report.severity === 'HIGH' ? 'Сындарлы' : 'Қауіп деңгейі') + ' · ' + decimal.format(estimate(report).risk) + ' / 10';
    $('estimate-risk').className = 'severity-badge severity-' + report.severity;
  }

  function exportOrder(report, address, coordinates) {
    const title = tr('Жұмыс нарядының жобасы');
    const place = [address, coordinates && (coordinates.latitude.toFixed(6) + ', ' + coordinates.longitude.toFixed(6))].filter(Boolean).join(' · ');
    const html = '<!doctype html><html lang="' + document.documentElement.lang + '"><meta charset="utf-8"><title>' + escape(title) +
      '</title><style>body{font:16px system-ui;max-width:700px;margin:40px auto;padding:20px}table{border-collapse:collapse;width:100%}th,td{padding:10px;border-bottom:1px solid #bbb;text-align:left}p{line-height:1.5}</style>' +
      '<h1>JolScan AI · ' + escape(title) + '</h1><p>' + escape(report.demo ? tr('ДЕМО') + ' · ' : '') + escape(report.source) +
      '</p><p>' + escape(place) + '</p><table>' + tableRows(report) + '</table><p>' + escape(tr('estimate_assumptions')) + '</p></html>';
    const url = URL.createObjectURL(new Blob([html], {type:'text/html;charset=utf-8'}));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'jolscan-work-order' + (report.demo ? '-demo' : '') + '.html';
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return {armSound, beep, demoResult, showPhotoOverlay, showEstimate, exportOrder};
})();
