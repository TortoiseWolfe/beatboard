/**
 * MAIN — UI wiring, mixer strip construction, event binding
 */
import { Engine } from './engine.js';
import { getMusicianForTrack, getPortraitPath, getLogoPath, getAllMusicians } from './band.js';

const engine = new Engine();
let mixLatched = false;

async function init() {
  await engine.init();
  buildMixer();
  populateJinglePicker();
  bindUI();

  engine.onTransport(playing => updatePlayButton(playing));
  engine.onTempo(tempo => updateTempoDisplay(tempo));
  engine.onStep(step => highlightStep(step));
  engine.onMasterLevel(level => updateMasterFader(level));
  engine.onPresetChange((name, patterns) => {
    updatePresetDisplay(name);
    rebuildMixerPatterns(patterns);
  });
  engine.onLearn((active, code, binding) => updateLearnUI(active, code, binding));
  engine.onLayerChange(layer => updateLayerUI(layer));
  engine.onLastPad(name => {
    const el = document.getElementById('lastPadDisplay');
    if (el) el.textContent = name;
  });
  engine.onTrackLaunch((trackNum, when, active) => {
    updateLaunchLights();
  });

  updatePlayButton(false);
  updateTempoDisplay(engine.tempo);
  updatePresetDisplay(engine.presetNames[engine.presetIndex]);
  renderBandList();
  loadPortraits();
}

function buildMixer() {
  const container = document.getElementById('mixerTracks');
  if (!container) return;
  container.innerHTML = '';

  // Tracks 1-4: Crash drum group with spanning header
  const crashCasting = getMusicianForTrack(1);
  const crash = crashCasting?.musician;
  const crashPortrait = crash ? getPortraitPath(crash.name) : '';

  const drumGroup = document.createElement('div');
  drumGroup.className = 'drum-group';
  drumGroup.innerHTML = `
    <div class="drum-group-header" tabindex="0" title="${crash?.personality || ''}">
      <div class="strip-portrait" style="background-image: url('${crashPortrait}')" role="img" aria-label="${crash?.look || 'Crash'}"></div>
      <div class="drum-group-meta">
        <div class="strip-name">${crash?.name || 'Crash'}</div>
        <div class="strip-role">${crash?.role || 'Pulse Engine'} (${crash?.instrument || 'Full drum kit'})</div>
      </div>
    </div>
    <div class="drum-strips-grid" id="drumStripsGrid"></div>
  `;
  container.appendChild(drumGroup);

  const drumStripsGrid = drumGroup.querySelector('#drumStripsGrid');
  for (let trackNum = 1; trackNum <= 4; trackNum++) {
    const track = engine.patterns[trackNum - 1];
    const strip = createTrackStripElement(trackNum, track, null, false);
    drumStripsGrid.appendChild(strip);
  }

  // Tracks 5 to 8
  for (let trackNum = 5; trackNum <= 8; trackNum++) {
    const track = engine.patterns[trackNum - 1];
    const casting = getMusicianForTrack(trackNum);
    const strip = createTrackStripElement(trackNum, track, casting, true);
    container.appendChild(strip);
  }

  attachMixerEventListeners(container);
  updateMuteSoloButtons();
  updateLaunchLights();
}

function createTrackStripElement(trackNum, track, casting, includeMusicianHeader) {
  const strip = document.createElement('div');
  strip.className = `mixer-track track-${trackNum}`;
  strip.dataset.track = trackNum;

  const musician = casting?.musician;
  const guest = casting?.guest;
  const portraitUrl = musician ? getPortraitPath(musician.name) : '';
  const guestPortraitUrl = guest ? getPortraitPath(guest.name) : '';
  const personality = musician ? musician.personality : '';

  let headerHtml = '';
  if (includeMusicianHeader && musician) {
    headerHtml = `
      <div class="strip-musician-header" tabindex="0" title="${personality}${guest ? ` | ${guest.name}: ${guest.personality}` : ''}">
        <div class="strip-portrait-wrap">
          <div class="strip-portrait" style="background-image: url('${portraitUrl}')" role="img" aria-label="${musician.look}"></div>
          ${guest ? `<div class="strip-portrait guest" style="background-image: url('${guestPortraitUrl}')" role="img" aria-label="${guest.look}"></div>` : ''}
        </div>
        <div class="strip-info">
          <div class="strip-name">${musician.name}${guest ? ` & ${guest.name}` : ''}</div>
          <div class="strip-role">${musician.role}${guest ? ` / ${guest.role}` : ''}</div>
        </div>
      </div>
    `;
  }

  const trackLevel = Math.round((track.level ?? track.volume ?? 0.7) * 100);

  strip.innerHTML = `
    ${headerHtml}
    <div class="strip-main">
      <div class="strip-top-row">
        <span class="track-number">Track ${trackNum} (${track.name})</span>
        <button class="strip-launch" data-track="${trackNum}" aria-label="Launch track ${trackNum}">
          <span class="launch-light"></span>
        </button>
      </div>
      <div class="strip-controls">
        <button class="btn-mute" data-track="${trackNum}" aria-label="Mute track ${trackNum}">M</button>
        <button class="btn-solo" data-track="${trackNum}" aria-label="Solo track ${trackNum}">S</button>
      </div>
      <div class="strip-fader-row">
        <input type="range" class="fader" data-track="${trackNum}" min="0" max="100" value="${trackLevel}" aria-label="Track ${trackNum} level">
        <span class="strip-value">${trackLevel}%</span>
      </div>
    </div>
  `;
  return strip;
}

function attachMixerEventListeners(container) {
  container.querySelectorAll('.strip-launch').forEach(btn => {
    btn.addEventListener('click', () => {
      const track = parseInt(btn.dataset.track);
      engine.launchOrStopTrack(track, null, false);
      updateLaunchLights();
    });
  });

  container.querySelectorAll('.btn-mute').forEach(btn => {
    btn.addEventListener('click', () => {
      const track = parseInt(btn.dataset.track);
      engine.toggleMute(track);
      updateMuteSoloButtons();
    });
  });

  container.querySelectorAll('.btn-solo').forEach(btn => {
    btn.addEventListener('click', () => {
      const track = parseInt(btn.dataset.track);
      engine.toggleSolo(track);
      updateMuteSoloButtons();
    });
  });

  container.querySelectorAll('.fader').forEach(fader => {
    fader.addEventListener('input', () => {
      const track = parseInt(fader.dataset.track);
      const targetLevel = parseInt(fader.value) / 100;
      const cur = engine.patterns[track - 1]?.level ?? engine.patterns[track - 1]?.volume ?? 0.7;
      engine.adjustLevel(track, targetLevel - cur);
      const valEl = fader.closest('.strip-main')?.querySelector('.strip-value');
      if (valEl) valEl.textContent = `${Math.round(targetLevel * 100)}%`;
    });
  });
}

function rebuildMixerPatterns(patterns) {
  patterns.forEach((track, i) => {
    const trackNum = i + 1;
    const fader = document.querySelector(`.fader[data-track="${trackNum}"]`);
    const valEl = fader?.closest('.strip-main')?.querySelector('.strip-value');
    const level = Math.round((track.level ?? track.volume ?? 0.7) * 100);
    if (fader) fader.value = level;
    if (valEl) valEl.textContent = `${level}%`;
  });
  updateMuteSoloButtons();
  updateLaunchLights();
}

function updateMuteSoloButtons() {
  document.querySelectorAll('.btn-mute').forEach(btn => {
    const track = parseInt(btn.dataset.track);
    const t = engine.patterns[track - 1];
    btn.classList.toggle('active', !!t?.muted);
  });
  document.querySelectorAll('.btn-solo').forEach(btn => {
    const track = parseInt(btn.dataset.track);
    const t = engine.patterns[track - 1];
    btn.classList.toggle('active', !!t?.solo);
  });
}

function updateLaunchLights() {
  document.querySelectorAll('.strip-launch').forEach(btn => {
    const track = parseInt(btn.dataset.track);
    const t = engine.patterns[track - 1];
    const light = btn.querySelector('.launch-light');
    if (light) {
      light.classList.toggle('active', !!t?.launched && !t?.muted);
    }
  });
}

function populateJinglePicker() {
  const picker = document.getElementById('jinglePicker');
  if (!picker) return;
  const takes = engine.getJingleTakes();
  picker.innerHTML = '';
  if (!takes.length) {
    const opt = document.createElement('option');
    opt.value = '';
    opt.textContent = 'Public Mode (drop audio file to load)';
    picker.appendChild(opt);
    return;
  }
  takes.forEach((t, i) => {
    const opt = document.createElement('option');
    opt.value = t.file;
    opt.textContent = `${t.label || t.file} (${t.kind || 'take'})`;
    picker.appendChild(opt);
  });
  engine.selectedJingleFile = takes[0]?.file || null;
  picker.addEventListener('change', () => {
    engine.selectedJingleFile = picker.value;
  });
}

function bindUI() {
  document.addEventListener('keydown', e => {
    engine.ensureAudioContext();
    if (e.code === 'Space' && !isTextInputFocused()) {
      e.preventDefault();
      if (!mixLatched) engine.setLayer('mix');
    }
    if (e.code === 'Tab' && !isTextInputFocused()) {
      e.preventDefault();
      mixLatched = !mixLatched;
      engine.setLayer(mixLatched ? 'mix' : 'play');
    }
    engine.handleKeyDown(e);
  });

  document.addEventListener('keyup', e => {
    if (e.code === 'Space' && !mixLatched) {
      engine.setLayer('play');
    }
    engine.handleKeyUp(e);
  });

  document.getElementById('btnPlay').addEventListener('click', () => {
    engine.ensureAudioContext();
    engine.toggleTransport();
  });
  document.getElementById('btnPresetPrev').addEventListener('click', () => {
    engine.ensureAudioContext();
    engine.changePreset(-1);
  });
  document.getElementById('btnPresetNext').addEventListener('click', () => {
    engine.ensureAudioContext();
    engine.changePreset(1);
  });
  document.getElementById('btnLearn').addEventListener('click', () => {
    engine.ensureAudioContext();
    engine.toggleLearnMode();
  });
  document.getElementById('btnBand').addEventListener('click', () => openBandDialog());

  document.getElementById('masterFader').addEventListener('input', e => {
    const val = parseInt(e.target.value) / 100;
    engine.changeMasterLevel(val - engine.masterLevel);
  });

  document.getElementById('closeBandDialog').addEventListener('click', () => closeBandDialog());
  document.getElementById('cancelLearn').addEventListener('click', () => {
    engine.learnMode.cancel();
    updateLearnUI(false);
  });

  document.getElementById('bandDialog').addEventListener('click', e => {
    if (e.target === e.currentTarget) closeBandDialog();
  });
  document.getElementById('learnDialog').addEventListener('click', e => {
    if (e.target === e.currentTarget) {
      engine.learnMode.cancel();
      updateLearnUI(false);
    }
  });

  document.querySelectorAll('.keycap').forEach(keycap => {
    keycap.addEventListener('click', () => handleKeycapClick(keycap));
    keycap.addEventListener('dragover', e => e.preventDefault());
    keycap.addEventListener('drop', e => handleDrop(e, keycap));
  });

  document.querySelectorAll('.mixer-track').forEach(strip => {
    strip.addEventListener('dragover', e => e.preventDefault());
    strip.addEventListener('drop', e => handleDrop(e, strip));
  });
}

function handleKeycapClick(keycap) {
  engine.ensureAudioContext();
  const track = parseInt(keycap.dataset.track);
  const pad = keycap.dataset.pad;
  const action = keycap.dataset.action;

  if (engine.learnMode.isActive()) {
    if (action === 'hit' || action === 'launch') {
      engine.learnMode.enter(action, track, pad);
      updateLearnUI(true);
    }
    return;
  }

  const kind = keycap.dataset.kind;
  if (action === 'hit') {
    engine.playHit(track, pad, {
      track,
      pad,
      note: keycap.dataset.note,
      sharpNote: keycap.dataset.sharpNote
    }, false);
    flashKeycap(keycap);
  } else if (action === 'launch') {
    engine.launchOrStopTrack(track, kind, false);
    flashKeycap(keycap);
    updateLaunchLights();
  }
}

function flashKeycap(keycap) {
  keycap.classList.add('playing');
  setTimeout(() => keycap.classList.remove('playing'), 120);
}

function highlightStep(step) {
  document.querySelectorAll('.keycap-row').forEach(row => {
    const trackNum = parseInt(row.dataset.track);
    const patternObj = engine.patterns[trackNum - 1];
    if (patternObj && patternObj.pattern && patternObj.pattern[step] === 1) {
      row.classList.add('step-active');
      setTimeout(() => row.classList.remove('step-active'), 50);
    }
  });
}

function updatePlayButton(playing) {
  const btn = document.getElementById('btnPlay');
  if (!btn) return;
  btn.textContent = playing ? '⏸' : '▶';
  btn.setAttribute('aria-label', playing ? 'Stop (Enter)' : 'Play (Enter)');
}

function updateTempoDisplay(tempo) {
  const el = document.getElementById('tempoDisplay');
  if (el) el.textContent = `${tempo} BPM`;
}

function updatePresetDisplay(name) {
  const el = document.getElementById('presetDisplay');
  if (el) el.textContent = name;
}

function updateMasterFader(level) {
  const fader = document.getElementById('masterFader');
  const val = document.getElementById('masterValue');
  if (fader) fader.value = Math.round(level * 100);
  if (val) val.textContent = `${Math.round(level * 100)}%`;
}

function updateLearnUI(active, code, binding) {
  const dialog = document.getElementById('learnDialog');
  const prompt = document.getElementById('learnPrompt');
  if (!dialog || !prompt) return;
  if (active) {
    dialog.showModal();
    prompt.textContent = 'Click a pad or control, then press a physical key…';
  } else if (code && binding) {
    prompt.textContent = `Assigned ${code} → ${binding.action} track ${binding.track || ''}${binding.pad ? ` (${binding.pad})` : ''}`;
    setTimeout(() => dialog.close(), 1200);
  } else {
    dialog.close();
  }
}

function updateLayerUI(layer) {
  const isMix = layer === 'mix';
  document.body.classList.toggle('mix-layer', isMix);
  const banner = document.getElementById('mixLayerBanner');
  if (banner) banner.style.display = isMix ? 'inline-block' : 'none';
}

function openBandDialog() {
  const dialog = document.getElementById('bandDialog');
  if (dialog) dialog.showModal();
}

function closeBandDialog() {
  const dialog = document.getElementById('bandDialog');
  if (dialog) dialog.close();
}

function renderBandList() {
  const list = document.getElementById('bandList');
  if (!list) return;
  const members = getAllMusicians();
  list.innerHTML = members.map(m => `
    <li>
      <img src="${getPortraitPath(m.name)}" alt="${m.look}" width="48" height="48">
      <div class="band-entry-info">
        <strong>${m.name}</strong> — ${m.instrument} (${m.role})
        <div class="personality">${m.personality}</div>
      </div>
    </li>
  `).join('');
}

function loadPortraits() {
  const logoEl = document.getElementById('portraitMaster');
  if (logoEl) {
    logoEl.style.backgroundImage = `url(${getLogoPath()})`;
  }
}

async function handleDrop(e, target) {
  e.preventDefault();
  engine.ensureAudioContext();
  const file = e.dataTransfer.files[0];
  if (!file || !file.type.startsWith('audio/')) return;

  let track = parseInt(target.dataset.track);
  if (isNaN(track)) {
    const strip = target.closest('.mixer-track');
    if (strip) track = parseInt(strip.dataset.track);
  }
  if (isNaN(track)) return;

  try {
    const arrayBuffer = await file.arrayBuffer();
    const buffer = await engine.actx.decodeAudioData(arrayBuffer);
    const trackObj = engine.patterns[track - 1];
    if (trackObj) {
      trackObj.userBuffer = buffer;
      trackObj.userBufferName = file.name;
      engine.setLastHitPad(`Loaded: ${file.name}`);
    }
  } catch (err) {
    console.error('Failed to decode dropped audio:', err);
  }
}

function isTextInputFocused() {
  const el = document.activeElement;
  if (!el) return false;
  const tag = el.tagName ? el.tagName.toLowerCase() : '';
  return tag === 'input' || tag === 'textarea' || tag === 'select' || el.isContentEditable;
}

init().catch(console.error);
