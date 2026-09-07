/**
 * GhostPad - cliente táctil estilo Pro Controller.
 * El estado se envía por WebSocket sólo cuando cambia.
 */
(() => {
  'use strict';

  /** Debe coincidir con protocol.py::Button */
  const BIT = Object.freeze({
    A: 0, B: 1, X: 2, Y: 3,
    L: 4, R: 5, ZL: 6, ZR: 7,
    MINUS: 8, PLUS: 9, LSTICK: 10, RSTICK: 11,
    HOME: 12, CAPTURE: 13,
    DPAD_UP: 14, DPAD_DOWN: 15, DPAD_LEFT: 16, DPAD_RIGHT: 17,
  });

  const SETTINGS_KEY = 'ghostpad-settings';
  const RECONNECT_MS = [400, 800, 1600, 3000];
  const DEFAULTS = {
    lang: 'es', layout: 'positional', vibrate: true, haptic: 'medium',
    deadzone: 8, sensitivity: 115, scale: 100, rstick: true, pin: '',
  };

  const $ = (id) => document.getElementById(id);

  // ============================================================ ajustes ==
  const settings = { ...DEFAULTS };
  try {
    Object.assign(settings, JSON.parse(localStorage.getItem(SETTINGS_KEY) || '{}'));
  } catch { /* almacenamiento bloqueado: valores por defecto */ }

  const persist = () => {
    try { localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings)); } catch { /* noop */ }
  };

  // ============================================================== idioma ==
  const I18N = Object.freeze({
    es: {
      'status.connecting': 'conectando…',
      'status.connected': 'conectado',
      'status.reconnecting': 'reconectando…',
      'status.full': 'mandos llenos',
      'status.pin': 'PIN incorrecto',
      'hud.fullscreen': 'Pantalla completa',
      'hud.settings': 'Ajustes',
      'gate.rotate.title': 'Gira el teléfono',
      'gate.rotate.text': 'Ponlo en horizontal para usar el mando. Toca el botón y lo intento girar por ti.',
      'gate.rotate.btn': 'Girar y continuar',
      'gate.fs.title': 'Todo listo',
      'gate.fs.text': 'Toca para volver al mando en pantalla completa.',
      'gate.fs.btn': 'Continuar',
      'gate.pin.title': 'Este mando pide un PIN',
      'gate.pin.text': 'Está en la consola del PC, junto al código QR.',
      'gate.pin.btn': 'Entrar',
      'gate.pin.error': 'PIN incorrecto, inténtalo otra vez.',
      'settings.title': 'Ajustes',
      'settings.lang': 'Idioma',
      'settings.lang.hint': 'Se guarda en este teléfono',
      'settings.sens': 'Sensibilidad del stick izquierdo',
      'settings.sens.hint': 'Más alto = llega al tope con menos recorrido',
      'settings.deadzone': 'Zona muerta',
      'settings.deadzone.hint': 'Súbela si el personaje se mueve solo',
      'settings.scale': 'Tamaño de los botones',
      'settings.vibrate': 'Vibración al pulsar',
      'settings.vibrate.hint': 'Al pulsar botones y con el rumble del juego',
      'settings.test': 'Probar',
      'settings.haptic': 'Fuerza de la vibración',
      'settings.haptic.hint': 'Si apenas la notas, sube a Fuerte',
      'settings.haptic.soft': 'Suave',
      'settings.haptic.medium': 'Media',
      'settings.haptic.strong': 'Fuerte',
      'settings.layout': 'Mapeo A/B/X/Y',
      'settings.layout.hint': 'Cámbialo solo si los botones salen invertidos',
      'settings.layout.positional': 'Por posición (Xbox estándar)',
      'settings.layout.nintendo': 'Por etiqueta (Nintendo)',
      'settings.rstick': 'Stick derecho visible',
      'settings.done': 'Listo',
      'vib.unsupported': 'Este navegador no soporta vibración (iPhone no la permite).',
      'vib.sent': '¿La sentiste? Si no, revisa que el teléfono no esté en silencio o con la vibración táctil apagada.',
      'vib.blocked': 'El navegador bloqueó la vibración. Toca cualquier botón del mando y prueba otra vez.',
    },
    en: {
      'status.connecting': 'connecting…',
      'status.connected': 'connected',
      'status.reconnecting': 'reconnecting…',
      'status.full': 'all pads taken',
      'status.pin': 'wrong PIN',
      'hud.fullscreen': 'Fullscreen',
      'hud.settings': 'Settings',
      'gate.rotate.title': 'Rotate your phone',
      'gate.rotate.text': 'Hold it in landscape to use the pad. Tap the button and I will try to rotate it for you.',
      'gate.rotate.btn': 'Rotate and continue',
      'gate.fs.title': 'Ready to play',
      'gate.fs.text': 'Tap to return to the pad in fullscreen.',
      'gate.fs.btn': 'Continue',
      'gate.pin.title': 'This pad asks for a PIN',
      'gate.pin.text': 'It is shown in the PC console, next to the QR code.',
      'gate.pin.btn': 'Enter',
      'gate.pin.error': 'Wrong PIN, try again.',
      'settings.title': 'Settings',
      'settings.lang': 'Language',
      'settings.lang.hint': 'Saved on this phone',
      'settings.sens': 'Left stick sensitivity',
      'settings.sens.hint': 'Higher = reaches full tilt with less travel',
      'settings.deadzone': 'Dead zone',
      'settings.deadzone.hint': 'Raise it if the character drifts on its own',
      'settings.scale': 'Button size',
      'settings.vibrate': 'Vibrate on press',
      'settings.vibrate.hint': 'On button presses and with in-game rumble',
      'settings.test': 'Test',
      'settings.haptic': 'Vibration strength',
      'settings.haptic.hint': 'If you barely feel it, set it to Strong',
      'settings.haptic.soft': 'Soft',
      'settings.haptic.medium': 'Medium',
      'settings.haptic.strong': 'Strong',
      'settings.layout': 'A/B/X/Y mapping',
      'settings.layout.hint': 'Change it only if the buttons come out swapped',
      'settings.layout.positional': 'By position (standard Xbox)',
      'settings.layout.nintendo': 'By label (Nintendo)',
      'settings.rstick': 'Show right stick',
      'settings.done': 'Done',
      'vib.unsupported': 'This browser does not support vibration (iPhone does not allow it).',
      'vib.sent': 'Did you feel it? If not, check that the phone is not on silent or has touch vibration off.',
      'vib.blocked': 'The browser blocked vibration. Tap any pad button and try again.',
    },
  });

  const t = (key) => I18N[settings.lang]?.[key] ?? I18N.es[key] ?? key;

  /** Vuelca las traducciones sobre los elementos con data-i18n / data-i18n-aria. */
  function applyLanguage() {
    document.documentElement.lang = settings.lang;
    document.querySelectorAll('[data-i18n]').forEach((el) => { el.textContent = t(el.dataset.i18n); });
    document.querySelectorAll('[data-i18n-aria]').forEach((el) => { el.setAttribute('aria-label', t(el.dataset.i18nAria)); });
    if (lastStatusKey) setStatus(lastStatusKey, lastStatusCls);
    gate.update();
  }

  // ============================================================= estado ==
  const state = { b: 0, lx: 0, ly: 0, rx: 0, ry: 0, zl: 0, zr: 0 };
  let lastSent = '';

  const setBit = (bit, down) => {
    if (down) state.b |= (1 << bit);
    else state.b &= ~(1 << bit);
  };

  /**
   * Vibración háptica. Los motores de muchos Android (ERM) no llegan a
   * arrancar con pulsos de ~10 ms: se sienten como nada. Por eso los pulsos
   * base rondan 30-40 ms y se escalan con el ajuste de fuerza.
   */
  const HAPTIC_GAIN = Object.freeze({ soft: 0.6, medium: 1, strong: 1.6 });
  const buzz = (ms) => {
    if (!settings.vibrate || typeof navigator.vibrate !== 'function') return false;
    const scaled = Math.round(ms * (HAPTIC_GAIN[settings.haptic] ?? 1));
    try { return navigator.vibrate(scaled); } catch { return false; }
  };

  const releaseAll = () => {
    Object.assign(state, { b: 0, lx: 0, ly: 0, rx: 0, ry: 0, zl: 0, zr: 0 });
    document.querySelectorAll('.on').forEach((el) => el.classList.remove('on'));
    document.querySelectorAll('.steer').forEach((el) => el.classList.remove('active'));
    document.querySelectorAll('.steer-nub').forEach((el) => { el.hidden = true; });
    document.querySelectorAll('.stick').forEach((el) => el.classList.remove('active'));
    document.querySelectorAll('.stick .stick-knob').forEach((el) => { el.style.transform = ''; });
  };

  // ========================================================== conexión ===
  const statusEl = $('status');
  const slotEl = $('slot-badge');
  let socket = null;
  let attempt = 0;

  let lastStatusKey = 'status.connecting';
  let lastStatusCls = '';
  const setStatus = (key, cls = '') => {
    lastStatusKey = key; lastStatusCls = cls;
    statusEl.textContent = t(key);
    statusEl.className = `status ${cls}`;
    gate.setConnection(t(key), cls === 'ok');
  };

  const sendConfig = () => {
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: 'config', layout: settings.layout }));
    }
  };

  // El PIN llega en la URL (desde el QR) y se recuerda en el teléfono.
  const urlPin = new URLSearchParams(location.search).get('pin');
  if (urlPin) { settings.pin = urlPin.trim(); persist(); }
  let pinRejected = false;

  function connect() {
    const scheme = location.protocol === 'https:' ? 'wss' : 'ws';
    const params = new URLSearchParams();
    const requested = new URLSearchParams(location.search).get('slot');
    if (requested) params.set('slot', requested);
    if (settings.pin) params.set('pin', settings.pin);
    const query = params.toString() ? `?${params}` : '';
    socket = new WebSocket(`${scheme}://${location.host}/ws${query}`);

    socket.addEventListener('open', () => {
      attempt = 0;
      lastSent = '';
      setStatus('status.connected', 'ok');
      sendConfig();
    });

    socket.addEventListener('message', (event) => {
      let msg;
      try { msg = JSON.parse(event.data); } catch { return; }
      if (msg.type === 'pong') {
        showPing(Math.round(performance.now() - (msg.t ?? pingSentAt)));
      } else if (msg.type === 'rumble') {
        rumble.apply(Number(msg.l) || 0, Number(msg.s) || 0);
      } else if (msg.type === 'assigned') {
        slotEl.textContent = `P${msg.slot}`;
        pinRejected = false;
        setStatus('status.connected', 'ok');
        gate.update();
      } else if (msg.type === 'rejected') {
        slotEl.textContent = '—';
        if (msg.reason === 'pin') {
          const again = pinRejected || gate.mode === 'pin';
          pinRejected = true;
          setStatus('status.pin', 'err');
          gate.update();
          if (again) {
            gate.text.textContent = t('gate.pin.error');
            gate.el.classList.add('error');
          }
        } else {
          setStatus('status.full', 'err');
        }
        socket.close();
      }
    });

    socket.addEventListener('close', () => {
      pingEl.hidden = true;
      if (pinRejected) return;              // esperamos a que escriban el PIN
      setStatus('status.reconnecting', 'err');
      setTimeout(connect, RECONNECT_MS[Math.min(attempt++, RECONNECT_MS.length - 1)]);
    });

    socket.addEventListener('error', () => socket.close());
  }

  // =============================================================== ping ==
  const pingEl = $('ping');
  let pingSentAt = 0;

  const showPing = (ms) => {
    pingEl.hidden = false;
    pingEl.textContent = `${ms} ms`;
    pingEl.className = `ping${ms > 90 ? ' bad' : ms > 45 ? ' warn' : ''}`;
  };

  setInterval(() => {
    if (socket?.readyState !== WebSocket.OPEN) return;
    pingSentAt = performance.now();
    socket.send(JSON.stringify({ type: 'ping', t: pingSentAt }));
  }, 2000);

  // ============================================================= rumble ==
  /** Traduce el rumble del juego a la vibración del teléfono. */
  const rumble = {
    until: 0,
    apply(large, small) {
      if (!settings.vibrate) return;
      const power = Math.max(large, small) / 255;
      if (power < 0.08) return;
      const now = performance.now();
      if (now < this.until) return;
      const ms = Math.round((30 + power * 70) * (HAPTIC_GAIN[settings.haptic] ?? 1));
      try { navigator.vibrate?.(ms); } catch { /* no soportado */ }
      this.until = now + ms + 25;
    },
  };

  function pump() {
    if (socket?.readyState === WebSocket.OPEN) {
      const payload = JSON.stringify(state);
      if (payload !== lastSent) {
        socket.send(payload);
        lastSent = payload;
      }
    }
    requestAnimationFrame(pump);
  }

  // ============================================================ botones ==
  /** data-btn admite varios botones a la vez separados por "+" (p. ej. "X+Y"). */
  function bindButton(el) {
    const names = el.dataset.btn.split('+').filter((n) => BIT[n] !== undefined);
    if (!names.length) return;
    const analogFor = (n) => (n === 'ZL' ? 'zl' : n === 'ZR' ? 'zr' : null);

    const press = (event) => {
      event.preventDefault();
      el.setPointerCapture?.(event.pointerId);
      el.classList.add('on');
      names.forEach((n) => {
        setBit(BIT[n], true);
        const a = analogFor(n); if (a) state[a] = 1;
      });
      buzz(35);
    };
    const release = () => {
      el.classList.remove('on');
      names.forEach((n) => {
        setBit(BIT[n], false);
        const a = analogFor(n); if (a) state[a] = 0;
      });
    };

    el.addEventListener('pointerdown', press);
    el.addEventListener('pointerup', release);
    el.addEventListener('pointercancel', release);
    el.addEventListener('lostpointercapture', release);
    el.addEventListener('contextmenu', (e) => e.preventDefault());
  }

  // ============================================================= sticks ==
  /**
   * Zona de stick. Con data-dynamic el centro nace donde tocas: el pulgar
   * nunca tiene que buscar el círculo, que es lo que cansa en un móvil.
   */
  function bindStick(el) {
    const axis = el.dataset.stick;
    const dynamic = el.dataset.dynamic === '1';
    const nub = el.querySelector('.steer-nub');          // sólo en la zona dinámica
    // Fracción del lado menor de la zona que equivale a stick a tope.
    const radiusFactor = Number(el.dataset.radius) || 0.28;
    const knob = nub ? nub.querySelector('.steer-cap') : el.querySelector('.stick-knob');
    const clickBit = axis === 'l' ? BIT.LSTICK : BIT.RSTICK;

    let pointerId = null;
    let origin = { x: 0, y: 0 };
    let radius = 60;   // radio de entrada: cuánto dedo equivale a tope de stick
    let travel = 30;   // radio visual: cuánto puede moverse la cabeza sin salirse
    let pressedAt = 0;

    const reset = () => {
      pointerId = null;
      state[`${axis}x`] = 0;
      state[`${axis}y`] = 0;
      el.classList.remove('active');
      setBit(clickBit, false);
      knob.style.transform = '';
      if (dynamic) nub.hidden = true;
    };

    const place = (event) => {
      const rect = el.getBoundingClientRect();
      if (dynamic) {
        radius = Math.min(rect.width, rect.height) * radiusFactor;
        origin = { x: event.clientX, y: event.clientY };
        nub.hidden = false;
        nub.style.left = `${origin.x - rect.left}px`;
        nub.style.top = `${origin.y - rect.top}px`;
        travel = (nub.offsetWidth - knob.offsetWidth) / 2;
      } else {
        radius = rect.width / 2;
        travel = radius * 0.5;
        origin = { x: rect.left + radius, y: rect.top + radius };
      }
    };

    const update = (event) => {
      let dx = (event.clientX - origin.x) / radius;
      let dy = -(event.clientY - origin.y) / radius;

      const mag = Math.hypot(dx, dy);
      if (mag > 1) { dx /= mag; dy /= mag; }

      const dead = settings.deadzone / 100;
      const norm = Math.min(mag, 1);
      if (norm < dead) {
        dx = 0; dy = 0;
      } else {
        const scaled = (norm - dead) / (1 - dead) / norm;
        dx *= scaled; dy *= scaled;
      }

      if (axis === 'l') {
        const gain = settings.sensitivity / 100;
        dx = Math.max(-1, Math.min(1, dx * gain));
        dy = Math.max(-1, Math.min(1, dy * gain));
      }

      state[`${axis}x`] = dx;
      state[`${axis}y`] = dy;

      knob.style.transform = `translate(${dx * travel}px, ${-dy * travel}px)`;
    };

    el.addEventListener('pointerdown', (event) => {
      event.preventDefault();
      pointerId = event.pointerId;
      pressedAt = performance.now();
      el.setPointerCapture(pointerId);
      el.classList.add('active');
      place(event);
      update(event);
    });

    el.addEventListener('pointermove', (event) => {
      if (event.pointerId === pointerId) update(event);
    });

    const end = (event) => {
      if (event.pointerId !== pointerId) return;
      const still = Math.hypot(state[`${axis}x`], state[`${axis}y`]) < 0.25;
      if (!dynamic && still && performance.now() - pressedAt < 180) {
        setBit(clickBit, true);
        buzz(45);
        setTimeout(() => setBit(clickBit, false), 60);
      }
      reset();
    };

    el.addEventListener('pointerup', end);
    el.addEventListener('pointercancel', end);
  }

  // =============================================================== dpad ==
  function bindDpad(el) {
    const zones = {
      DPAD_UP: el.querySelector('.dpad-dir.up'),
      DPAD_DOWN: el.querySelector('.dpad-dir.down'),
      DPAD_LEFT: el.querySelector('.dpad-dir.left'),
      DPAD_RIGHT: el.querySelector('.dpad-dir.right'),
    };
    const THRESHOLD = 0.22;
    let pointerId = null;
    let lastMask = 0;

    const clear = () => {
      Object.entries(zones).forEach(([name, node]) => {
        node.classList.remove('on');
        setBit(BIT[name], false);
      });
      lastMask = 0;
    };

    const update = (event) => {
      const rect = el.getBoundingClientRect();
      const dx = (event.clientX - (rect.left + rect.width / 2)) / (rect.width / 2);
      const dy = (event.clientY - (rect.top + rect.height / 2)) / (rect.height / 2);
      const active = {
        DPAD_UP: dy < -THRESHOLD,
        DPAD_DOWN: dy > THRESHOLD,
        DPAD_LEFT: dx < -THRESHOLD,
        DPAD_RIGHT: dx > THRESHOLD,
      };
      let mask = 0;
      Object.entries(active).forEach(([name, on], index) => {
        zones[name].classList.toggle('on', on);
        setBit(BIT[name], on);
        if (on) mask |= (1 << index);
      });
      if (mask && mask !== lastMask) buzz(28);
      lastMask = mask;
    };

    el.addEventListener('pointerdown', (event) => {
      event.preventDefault();
      pointerId = event.pointerId;
      el.setPointerCapture(pointerId);
      update(event);
    });
    el.addEventListener('pointermove', (event) => {
      if (event.pointerId === pointerId) update(event);
    });
    const end = (event) => {
      if (event.pointerId !== pointerId) return;
      pointerId = null;
      clear();
    };
    el.addEventListener('pointerup', end);
    el.addEventListener('pointercancel', end);
  }

  document.querySelectorAll('[data-btn]').forEach(bindButton);
  document.querySelectorAll('[data-stick]').forEach(bindStick);
  document.querySelectorAll('.dpad').forEach(bindDpad);

  // =========================================================== ajustes ===
  const dialog = $('settings');
  const inputs = {
    lang: $('opt-lang'),
    haptic: $('opt-haptic'),
    layout: $('opt-layout'),
    vibrate: $('opt-vibrate'),
    deadzone: $('opt-deadzone'),
    sensitivity: $('opt-sens'),
    scale: $('opt-scale'),
    rstick: $('opt-rstick'),
  };

  const applySettings = () => {
    inputs.lang.value = I18N[settings.lang] ? settings.lang : 'es';
    inputs.haptic.value = HAPTIC_GAIN[settings.haptic] ? settings.haptic : 'medium';
    inputs.layout.value = settings.layout;
    inputs.vibrate.checked = settings.vibrate;
    inputs.deadzone.value = settings.deadzone;
    inputs.sensitivity.value = settings.sensitivity;
    inputs.scale.value = settings.scale;
    inputs.rstick.checked = settings.rstick;
    document.documentElement.style.setProperty('--scale', settings.scale / 100);
    $('stick-r').classList.toggle('hidden', !settings.rstick);
  };

  inputs.lang.addEventListener('change', () => {
    settings.lang = inputs.lang.value;
    persist();
    applyLanguage();
  });
  inputs.haptic.addEventListener('change', () => {
    settings.haptic = inputs.haptic.value;
    persist();
    buzz(60);
  });
  inputs.layout.addEventListener('change', () => {
    settings.layout = inputs.layout.value;
    persist();
    sendConfig();
  });
  inputs.vibrate.addEventListener('change', () => { settings.vibrate = inputs.vibrate.checked; persist(); });
  inputs.deadzone.addEventListener('input', () => { settings.deadzone = Number(inputs.deadzone.value); persist(); });
  inputs.sensitivity.addEventListener('input', () => { settings.sensitivity = Number(inputs.sensitivity.value); persist(); });
  inputs.scale.addEventListener('input', () => {
    settings.scale = Number(inputs.scale.value);
    document.documentElement.style.setProperty('--scale', settings.scale / 100);
    persist();
  });
  inputs.rstick.addEventListener('change', () => {
    settings.rstick = inputs.rstick.checked;
    $('stick-r').classList.toggle('hidden', !settings.rstick);
    persist();
  });

  // Prueba de vibración: confirma soporte del navegador y que el modo silencio
  // del teléfono no la esté bloqueando.
  $('vib-test').addEventListener('click', () => {
    const note = $('vib-note');
    if (typeof navigator.vibrate !== 'function') {
      note.textContent = t('vib.unsupported');
      return;
    }
    const gain = HAPTIC_GAIN[settings.haptic] ?? 1;
    const ok = navigator.vibrate([60, 70, 60, 70, 140].map((v, i) => (i % 2 ? v : Math.round(v * gain))));
    note.textContent = ok ? t('vib.sent') : t('vib.blocked');
  });

  $('settings-btn').addEventListener('click', () => dialog.showModal());
  $('settings-close').addEventListener('click', () => dialog.close());

  // ========================================================== arranque ===
  /**
   * Mantiene la pantalla encendida. La Wake Lock API exige HTTPS, así que en
   * red local se recurre a un vídeo mudo en bucle: mientras se reproduce, el
   * móvil no se duerme.
   */
  const screenAwake = {
    lock: null,
    video: $('nosleep'),
    async enable() {
      try {
        this.lock = await navigator.wakeLock?.request?.('screen');
        if (this.lock) {
          this.lock.addEventListener?.('release', () => { this.lock = null; });
          return;
        }
      } catch { /* sin https: pasamos al vídeo */ }
      try { await this.video.play(); } catch { /* requiere gesto del usuario */ }
    },
    async refresh() {
      if (!this.lock && this.video.paused) await this.enable();
    },
  };

  async function goFullscreen() {
    await screenAwake.enable();
    if (!document.fullscreenElement) {
      try { await document.documentElement.requestFullscreen({ navigationUI: 'hide' }); } catch { /* opcional */ }
    }
    try { await screen.orientation?.lock?.('landscape'); } catch { /* iOS no lo permite */ }
  }

  /**
   * Compuerta: tapa el mando cuando el teléfono está en vertical o cuando se
   * perdió la pantalla completa (al volver de otra app). El botón es el gesto
   * que el navegador exige para girar la pantalla y ponerla completa.
   */
  const gate = {
    el: $('gate'),
    title: $('gate-title'),
    text: $('gate-text'),
    btn: $('gate-btn'),
    conn: $('gate-conn'),
    touch: matchMedia('(pointer: coarse)').matches,
    portrait: matchMedia('(orientation: portrait)'),
    canFullscreen: !!document.fullscreenEnabled,

    setConnection(text, online) {
      this.conn.textContent = text;
      this.el.classList.toggle('online', online);
    },

    pinInput: $('gate-pin'),
    mode: 'none',

    update() {
      const portrait = this.portrait.matches;
      const needsFs = this.touch && this.canFullscreen && !document.fullscreenElement;
      if (pinRejected) {
        this.show('pin', t('gate.pin.title'), t('gate.pin.text'), t('gate.pin.btn'), true);
      } else if (this.touch && portrait) {
        this.show('rotate', t('gate.rotate.title'), t('gate.rotate.text'), t('gate.rotate.btn'), false);
      } else if (needsFs) {
        this.show('fs', t('gate.fs.title'), t('gate.fs.text'), t('gate.fs.btn'), true);
      } else {
        this.hide();
      }
    },

    show(mode, title, text, label, landscape) {
      this.mode = mode;
      this.title.textContent = title;
      this.text.textContent = text;
      this.btn.textContent = label;
      this.el.classList.toggle('landscape', landscape);
      this.pinInput.hidden = mode !== 'pin';
      if (mode === 'pin') {
        this.pinInput.value = settings.pin || '';
        setTimeout(() => this.pinInput.focus(), 50);
      }
      if (this.el.hidden) {
        releaseAll();
        this.el.hidden = false;
      }
    },

    submitPin() {
      const value = this.pinInput.value.trim();
      if (!value) { this.pinInput.focus(); return; }
      settings.pin = value;
      persist();
      pinRejected = false;
      this.el.classList.remove('error');
      setStatus('status.connecting');
      connect();
    },

    hide() { this.el.hidden = true; },
  };

  gate.btn.addEventListener('click', async () => {
    if (gate.mode === 'pin') { gate.submitPin(); return; }
    await goFullscreen();
    // La orientación puede tardar un instante en cambiar tras el bloqueo.
    setTimeout(() => gate.update(), 350);
  });
  gate.pinInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') gate.submitPin(); });
  gate.portrait.addEventListener('change', () => gate.update());
  document.addEventListener('fullscreenchange', () => gate.update());
  window.addEventListener('resize', () => gate.update());
  $('fs-btn').addEventListener('click', goFullscreen);

  // Soltar todo al perder el foco: nadie quiere volver y seguir acelerando.
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      releaseAll();
    } else {
      screenAwake.refresh();
      gate.update();
    }
  });

  document.addEventListener('gesturestart', (e) => e.preventDefault());
  document.addEventListener('dblclick', (e) => e.preventDefault());

  applySettings();
  applyLanguage();
  connect();
  requestAnimationFrame(pump);
})();
