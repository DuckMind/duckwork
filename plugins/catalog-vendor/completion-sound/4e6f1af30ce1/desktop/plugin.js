// src/plugin.jsx
import * as sdk from "@duckwork/plugin-sdk";
import { useRef, useState } from "react";

// src/vendor/audio-context.ts
var ctx = null;
function getAudioContext() {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    if (!ctx) {
      const Ctor = window.AudioContext || window.webkitAudioContext;
      if (!Ctor) {
        return null;
      }
      ctx = new Ctor();
    }
    if (ctx.state === "suspended") {
      void ctx.resume().catch(() => void 0);
    }
    return ctx;
  } catch {
    return null;
  }
}

// src/vendor/shims/completion-store.js
var $completionSoundVariantId = { get: () => 1 };
function resolveCompletionSoundVariantId(v) {
  return Number.isInteger(v) && v >= 1 && v <= 14 ? v : 1;
}

// src/vendor/completion-sound.ts
function voice(ac, master, t0, spec) {
  const osc = ac.createOscillator();
  const env = ac.createGain();
  const start = t0 + (spec.start ?? 0);
  const peak = spec.gain ?? 0.5;
  const attack = spec.attack ?? 6e-3;
  const end = start + spec.dur;
  osc.type = spec.type ?? "sine";
  osc.frequency.setValueAtTime(spec.freq, start);
  env.gain.setValueAtTime(1e-4, start);
  env.gain.exponentialRampToValueAtTime(Math.max(peak, 2e-4), start + attack);
  env.gain.exponentialRampToValueAtTime(1e-4, end);
  osc.connect(env);
  env.connect(master);
  osc.start(start);
  osc.stop(end + 0.02);
}
function pluckVoice(ac, master, t0, spec) {
  const osc = ac.createOscillator();
  const env = ac.createGain();
  const start = t0 + (spec.start ?? 0);
  const attack = spec.attack ?? 4e-3;
  const glide = spec.glide ?? 0.16;
  const end = start + spec.decay;
  osc.type = "triangle";
  osc.frequency.setValueAtTime(spec.freqFrom, start);
  osc.frequency.exponentialRampToValueAtTime(spec.freqTo, start + glide);
  env.gain.setValueAtTime(1e-4, start);
  env.gain.exponentialRampToValueAtTime(Math.max(spec.gain, 2e-4), start + attack);
  env.gain.exponentialRampToValueAtTime(1e-4, end);
  osc.connect(env);
  env.connect(master);
  osc.start(start);
  osc.stop(end + 0.02);
}
function bloomVoice(ac, master, t0, spec) {
  const osc = ac.createOscillator();
  const env = ac.createGain();
  const start = t0 + (spec.start ?? 0);
  const hold = spec.hold ?? 0.08;
  const end = start + spec.attack + hold + spec.decay;
  osc.type = spec.type ?? "sine";
  osc.frequency.setValueAtTime(spec.freq, start);
  if (spec.freqTo) {
    osc.frequency.exponentialRampToValueAtTime(spec.freqTo, start + spec.attack + hold * 0.6);
  }
  osc.detune.setValueAtTime(spec.detune ?? 0, start);
  env.gain.setValueAtTime(1e-4, start);
  env.gain.exponentialRampToValueAtTime(Math.max(spec.gain, 2e-4), start + spec.attack);
  env.gain.setValueAtTime(Math.max(spec.gain, 2e-4), start + spec.attack + hold);
  env.gain.exponentialRampToValueAtTime(1e-4, end);
  osc.connect(env);
  env.connect(master);
  osc.start(start);
  osc.stop(end + 0.02);
}
function noiseSource(ac, seconds) {
  const length = Math.floor(ac.sampleRate * seconds);
  const buffer = ac.createBuffer(1, length, ac.sampleRate);
  const data = buffer.getChannelData(0);
  for (let i = 0; i < length; i += 1) {
    data[i] = Math.random() * 2 - 1;
  }
  const source = ac.createBufferSource();
  source.buffer = buffer;
  return source;
}
function airPuff(ac, master, t0, spec) {
  const source = noiseSource(ac, 0.12);
  const filter = ac.createBiquadFilter();
  const env = ac.createGain();
  const start = t0 + (spec.start ?? 0);
  const end = start + spec.decay;
  filter.type = "bandpass";
  filter.frequency.setValueAtTime(spec.freq, start);
  filter.Q.setValueAtTime(spec.q ?? 1.2, start);
  env.gain.setValueAtTime(1e-4, start);
  env.gain.exponentialRampToValueAtTime(Math.max(spec.gain, 2e-4), start + 0.018);
  env.gain.exponentialRampToValueAtTime(1e-4, end);
  source.connect(filter);
  filter.connect(env);
  env.connect(master);
  source.start(start);
  source.stop(end + 0.02);
}
function whooshVoice(ac, master, t0, spec) {
  const source = noiseSource(ac, 0.4);
  const filter = ac.createBiquadFilter();
  const env = ac.createGain();
  const start = t0 + (spec.start ?? 0);
  const end = start + spec.decay;
  filter.type = "bandpass";
  filter.frequency.setValueAtTime(spec.freqFrom, start);
  filter.frequency.exponentialRampToValueAtTime(spec.freqTo, end);
  filter.Q.setValueAtTime(spec.q ?? 0.8, start);
  env.gain.setValueAtTime(1e-4, start);
  env.gain.exponentialRampToValueAtTime(Math.max(spec.gain, 2e-4), start + 0.03);
  env.gain.exponentialRampToValueAtTime(1e-4, end);
  source.connect(filter);
  filter.connect(env);
  env.connect(master);
  source.start(start);
  source.stop(end + 0.02);
}
function sweepVoice(ac, master, t0, spec) {
  const osc = ac.createOscillator();
  const env = ac.createGain();
  const start = t0 + (spec.start ?? 0);
  const attack = spec.attack ?? 3e-3;
  const end = start + spec.decay;
  osc.type = spec.type ?? "triangle";
  osc.frequency.setValueAtTime(spec.freqFrom, start);
  osc.frequency.exponentialRampToValueAtTime(spec.freqTo, end - 0.02);
  env.gain.setValueAtTime(1e-4, start);
  env.gain.exponentialRampToValueAtTime(Math.max(spec.gain, 2e-4), start + attack);
  env.gain.exponentialRampToValueAtTime(1e-4, end);
  osc.connect(env);
  env.connect(master);
  osc.start(start);
  osc.stop(end + 0.02);
}
var reverbImpulse = null;
function makeReverb(ac) {
  if (!reverbImpulse) {
    const seconds = 1.6;
    const length = Math.floor(ac.sampleRate * seconds);
    reverbImpulse = ac.createBuffer(2, length, ac.sampleRate);
    for (let channel = 0; channel < 2; channel += 1) {
      const data = reverbImpulse.getChannelData(channel);
      for (let i = 0; i < length; i += 1) {
        data[i] = (Math.random() * 2 - 1) * (1 - i / length) ** 2.6;
      }
    }
  }
  const convolver = ac.createConvolver();
  convolver.buffer = reverbImpulse;
  return convolver;
}
var A2 = 110;
var A3 = 220;
var A4 = 440;
var A5 = 880;
var B5 = 987.77;
var C3 = 130.81;
var C4 = 261.63;
var E4 = 329.63;
var E5 = 659.25;
var E6 = 1318.51;
var G4 = 392;
var G5 = 783.99;
var C5 = 523.25;
var C6 = 1046.5;
var COMPLETION_SOUND_VARIANTS = [
  {
    id: 1,
    name: "Two-note comfort",
    play: (ac, master, t0) => {
      voice(ac, master, t0, { freq: E4, dur: 0.22, gain: 0.05, attack: 0.03, type: "sine" });
      voice(ac, master, t0 + 0.08, { freq: C4, dur: 0.52, gain: 0.07, attack: 0.08, type: "sine" });
      voice(ac, master, t0 + 0.08, { freq: C3, dur: 0.46, gain: 0.02, attack: 0.1, type: "sine" });
    }
  },
  {
    id: 2,
    name: "Glass ping",
    play: (ac, master, t0) => {
      voice(ac, master, t0, { freq: C6, dur: 0.55, gain: 0.032, attack: 2e-3, type: "sine" });
      voice(ac, master, t0 + 0.01, { freq: E5, dur: 0.42, gain: 0.018, attack: 4e-3, type: "sine" });
      airPuff(ac, master, t0, { freq: 3200, gain: 4e-3, decay: 0.1, q: 1.4 });
    }
  },
  {
    id: 3,
    name: "Soft marimba",
    play: (ac, master, t0) => {
      pluckVoice(ac, master, t0, { freqFrom: E5, freqTo: G5, gain: 0.03, decay: 0.14, glide: 0.08 });
      bloomVoice(ac, master, t0 + 0.04, { freq: C5, gain: 0.028, attack: 0.08, hold: 0.04, decay: 0.62 });
      bloomVoice(ac, master, t0 + 0.06, { freq: G4, gain: 0.014, attack: 0.12, hold: 0.06, decay: 0.55 });
    }
  },
  {
    id: 4,
    name: "Tri-tone message",
    play: (ac, master, t0) => {
      voice(ac, master, t0, { freq: C6, dur: 0.14, gain: 0.045, attack: 4e-3, type: "sine" });
      voice(ac, master, t0 + 0.1, { freq: A5, dur: 0.16, gain: 0.04, attack: 4e-3, type: "sine" });
      voice(ac, master, t0 + 0.2, { freq: G5, dur: 0.22, gain: 0.035, attack: 6e-3, type: "sine" });
    }
  },
  {
    id: 5,
    name: "Airy whoosh",
    play: (ac, master, t0) => {
      whooshVoice(ac, master, t0, { freqFrom: 4200, freqTo: 900, gain: 0.022, decay: 0.28, q: 0.7 });
      voice(ac, master, t0 + 0.12, { freq: A5, dur: 0.35, gain: 0.02, attack: 0.02, type: "sine" });
    }
  },
  {
    id: 6,
    name: "Discovery cluster",
    play: (ac, master, t0) => {
      const clusterDetunes = [-14, -5, 0, 7, 12];
      clusterDetunes.forEach((detune, i) => {
        bloomVoice(ac, master, t0 + i * 0.03, {
          freq: A3,
          gain: 0.012,
          attack: 0.38,
          hold: 0.12,
          decay: 1.05,
          detune
        });
      });
      bloomVoice(ac, master, t0 + 0.1, { freq: E4, gain: 8e-3, attack: 0.45, hold: 0.08, decay: 0.9, detune: 3 });
    }
  },
  {
    id: 7,
    name: "Systems online",
    play: (ac, master, t0) => {
      voice(ac, master, t0, { freq: C5, dur: 0.16, gain: 0.04, attack: 6e-3, type: "sine" });
      voice(ac, master, t0 + 0.09, { freq: G5, dur: 0.28, gain: 0.042, attack: 8e-3, type: "sine" });
      voice(ac, master, t0 + 0.09, { freq: C4, dur: 0.24, gain: 0.012, attack: 0.01, type: "sine" });
    }
  },
  {
    id: 8,
    name: "IBM terminal",
    play: (ac, master, t0) => {
      voice(ac, master, t0, { freq: B5, dur: 0.12, gain: 0.038, attack: 2e-3, type: "square" });
      voice(ac, master, t0 + 0.14, { freq: E5, dur: 0.1, gain: 0.028, attack: 2e-3, type: "square" });
    }
  },
  {
    id: 9,
    name: "Modem chirp",
    play: (ac, master, t0) => {
      sweepVoice(ac, master, t0, { freqFrom: 320, freqTo: 2200, gain: 0.024, decay: 0.16, type: "triangle" });
      sweepVoice(ac, master, t0 + 0.1, { freqFrom: 480, freqTo: 1400, gain: 0.014, decay: 0.12, type: "sine" });
    }
  },
  {
    id: 10,
    name: "Wind chimes",
    play: (ac, master, t0) => {
      const chimes = [G5, C6, E5, A5];
      chimes.forEach((frequency, i) => {
        voice(ac, master, t0 + i * 0.13, {
          freq: frequency,
          dur: 0.72,
          gain: 0.028 - i * 3e-3,
          attack: 3e-3,
          type: "sine"
        });
      });
    }
  },
  {
    id: 11,
    name: "Singing bowl",
    play: (ac, master, t0) => {
      bloomVoice(ac, master, t0, { freq: A3, gain: 0.022, attack: 0.58, hold: 0.16, decay: 1.35 });
      bloomVoice(ac, master, t0 + 0.08, { freq: E4, gain: 0.01, attack: 0.62, hold: 0.12, decay: 1.2, detune: 4 });
      bloomVoice(ac, master, t0 + 0.14, { freq: A4, gain: 6e-3, attack: 0.68, hold: 0.08, decay: 1.05, detune: -3 });
    }
  },
  {
    id: 12,
    name: "Harp lift",
    play: (ac, master, t0) => {
      const notes = [C5, E5, G5, C6];
      notes.forEach((frequency, i) => {
        voice(ac, master, t0 + i * 0.075, {
          freq: frequency,
          dur: 0.38,
          gain: 0.034 - i * 4e-3,
          attack: 0.012,
          type: "sine"
        });
      });
      bloomVoice(ac, master, t0 + 0.2, { freq: C4, gain: 0.01, attack: 0.18, hold: 0.06, decay: 0.7 });
    }
  },
  {
    id: 13,
    name: "Sonar ping",
    play: (ac, master, t0) => {
      voice(ac, master, t0, { freq: A2, dur: 0.95, gain: 0.036, attack: 8e-3, type: "sine" });
      voice(ac, master, t0 + 0.42, { freq: A3, dur: 0.55, gain: 0.014, attack: 0.01, type: "sine" });
      airPuff(ac, master, t0, { freq: 600, gain: 5e-3, decay: 0.2, q: 0.5 });
    }
  },
  {
    id: 14,
    name: "Music box",
    play: (ac, master, t0) => {
      const notes = [E6, C6, G5, E5];
      notes.forEach((frequency, i) => {
        pluckVoice(ac, master, t0 + i * 0.09, {
          freqFrom: frequency,
          freqTo: frequency * 0.998,
          gain: 0.02 - i * 2e-3,
          decay: 0.2,
          glide: 0.06
        });
      });
    }
  }
];
function playVariant(variantId) {
  const variant = COMPLETION_SOUND_VARIANTS.find((v) => v.id === variantId);
  if (!variant) {
    return;
  }
  const ac = getAudioContext();
  if (!ac) {
    return;
  }
  const master = ac.createGain();
  const tone = ac.createBiquadFilter();
  tone.type = "lowpass";
  tone.frequency.setValueAtTime(3800, ac.currentTime);
  tone.Q.setValueAtTime(0.32, ac.currentTime);
  master.gain.setValueAtTime(0.48, ac.currentTime);
  master.connect(tone);
  const dry = ac.createGain();
  dry.gain.setValueAtTime(0.88, ac.currentTime);
  tone.connect(dry);
  dry.connect(ac.destination);
  const reverb = makeReverb(ac);
  const wet = ac.createGain();
  wet.gain.setValueAtTime(0.34, ac.currentTime);
  tone.connect(reverb);
  reverb.connect(wet);
  wet.connect(ac.destination);
  variant.play(ac, master, ac.currentTime + 0.01);
}
function previewCompletionSound(variantId) {
  playVariant(resolveCompletionSoundVariantId(variantId ?? $completionSoundVariantId.get()));
}

// src/messages.js
var messages_default = {
  en: {
    preview: "Preview",
    sound: {
      title: "Completion sound",
      description: "Plays when a turn finishes.",
      none: "No sound",
      myFiles: "My files",
      presets: "Duckwork presets"
    },
    night: {
      title: "Different sound at night",
      description: "Use another sound during the hours below.",
      hours: "Night hours",
      sound: "Night sound"
    },
    files: {
      title: "My audio files",
      description: (max, kb) => `Add up to ${max} files (mp3, wav, ogg, \u2026), ${kb} KB each.`,
      add: "Add file\u2026",
      remove: "Remove",
      tooMany: (max) => `You can keep up to ${max} files. Remove one first.`,
      tooBig: (kb) => `The file is larger than ${kb} KB.`,
      saveFailed: (reason) => `Could not save the file: ${reason}`
    },
    volume: {
      title: "File volume",
      description: "Applies to your files. Presets play at Duckwork\u2019 own level."
    },
    note: {
      builtin: "Duckwork\u2019 own completion sound still plays alongside this one: Duckwork has no setting to turn it off yet, and plugins cannot switch it off."
    }
  },
  ko: {
    preview: "\uBBF8\uB9AC\uB4E3\uAE30",
    sound: {
      title: "\uC644\uB8CC \uC18C\uB9AC",
      description: "\uC751\uB2F5\uC774 \uB05D\uB098\uBA74 \uB09C\uB2E4.",
      none: "\uC18C\uB9AC \uC5C6\uC74C",
      myFiles: "\uB0B4 \uD30C\uC77C",
      presets: "Duckwork \uAE30\uBCF8 \uC18C\uB9AC"
    },
    night: {
      title: "\uBC24\uC5D0\uB294 \uB2E4\uB978 \uC18C\uB9AC",
      description: "\uC544\uB798 \uC2DC\uAC04\uB300\uC5D0\uB294 \uB2E4\uB978 \uC18C\uB9AC\uB97C \uB0B8\uB2E4.",
      hours: "\uC57C\uAC04 \uC2DC\uAC04\uB300",
      sound: "\uC57C\uAC04 \uC18C\uB9AC"
    },
    files: {
      title: "\uB0B4 \uC18C\uB9AC \uD30C\uC77C",
      description: (max, kb) => `\uD30C\uC77C\uC744 ${max}\uAC1C\uAE4C\uC9C0 \uB123\uC744 \uC218 \uC788\uB2E4(mp3, wav, ogg \uB4F1, \uD30C\uC77C\uB2F9 ${kb} KB).`,
      add: "\uD30C\uC77C \uCD94\uAC00\u2026",
      remove: "\uC0AD\uC81C",
      tooMany: (max) => `\uD30C\uC77C\uC740 ${max}\uAC1C\uAE4C\uC9C0 \uB123\uC744 \uC218 \uC788\uB2E4. \uD558\uB098\uB97C \uBA3C\uC800 \uC9C0\uC6CC\uB77C.`,
      tooBig: (kb) => `\uD30C\uC77C\uC774 ${kb} KB\uBCF4\uB2E4 \uD06C\uB2E4.`,
      saveFailed: (reason) => `\uD30C\uC77C\uC744 \uC800\uC7A5\uD558\uC9C0 \uBABB\uD588\uB2E4: ${reason}`
    },
    volume: {
      title: "\uD30C\uC77C \uC74C\uB7C9",
      description: "\uB0B4 \uD30C\uC77C\uC5D0\uB9CC \uC801\uC6A9\uB41C\uB2E4. \uAE30\uBCF8 \uC18C\uB9AC\uB294 Duckwork\uAC00 \uC815\uD55C \uC74C\uB7C9\uC73C\uB85C \uB09C\uB2E4."
    },
    note: {
      builtin: "Duckwork \uC790\uCCB4 \uC644\uB8CC \uC18C\uB9AC\uB3C4 \uD568\uAED8 \uB09C\uB2E4. Duckwork\uC5D0\uB294 \uC544\uC9C1 \uC774 \uC18C\uB9AC\uB97C \uB044\uB294 \uC124\uC815\uC774 \uC5C6\uACE0, \uD50C\uB7EC\uADF8\uC778\uC774 \uB04C \uC218\uB3C4 \uC5C6\uB2E4."
    }
  }
};

// src/plugin.jsx
import { Fragment, jsx, jsxs } from "react/jsx-runtime";
var { Button, ListRow, ToggleRow, usePluginI18n } = sdk;
var ID = "completion-sound";
var MAX_FILES = 3;
var MAX_FILE_BYTES = 1024 * 1024;
var MIN_GAP_MS = 1500;
var DEFAULTS = {
  sound: "preset:1",
  nightEnabled: false,
  nightSound: "preset:3",
  nightStart: "22:00",
  nightEnd: "07:00",
  volume: 0.8
};
var ctxRef = null;
var lastPlayedAt = 0;
var loadConfig = () => ({ ...DEFAULTS, ...ctxRef.storage.get("config", {}) });
var saveConfig = (patch) => {
  const next = { ...loadConfig(), ...patch };
  ctxRef.storage.set("config", next);
  return next;
};
var loadFiles = () => ctxRef.storage.get("files", []);
var saveFiles = (files) => ctxRef.storage.set("files", files);
function minutes(hhmm) {
  const [h, m] = String(hhmm).split(":").map(Number);
  return (Number.isFinite(h) ? h : 0) * 60 + (Number.isFinite(m) ? m : 0);
}
function isNight(cfg, now = /* @__PURE__ */ new Date()) {
  if (!cfg.nightEnabled) return false;
  const t = now.getHours() * 60 + now.getMinutes();
  const a = minutes(cfg.nightStart);
  const b = minutes(cfg.nightEnd);
  return a <= b ? t >= a && t < b : t >= a || t < b;
}
var soundNow = (cfg) => isNight(cfg) ? cfg.nightSound : cfg.sound;
function play(sound, volume) {
  if (!sound || sound === "none") return;
  const sep = sound.indexOf(":");
  const kind = sound.slice(0, sep);
  const id = sound.slice(sep + 1);
  if (kind === "preset") {
    previewCompletionSound(Number(id));
    return;
  }
  if (kind === "file") {
    const file = loadFiles().find((f) => f.id === id);
    if (!file) return;
    const audio = new Audio(file.dataUrl);
    audio.volume = Math.max(0, Math.min(1, Number(volume) || 0));
    audio.play().catch((err) => console.warn("[completion-sound] playback failed", err));
  }
}
function readFile(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}
var control = "rounded-md border border-border bg-transparent px-2 py-1 text-sm";
function SoundSelect({ files, onChange, t, value }) {
  return /* @__PURE__ */ jsxs("select", { className: `min-w-56 ${control}`, onChange: (e) => onChange(e.target.value), value, children: [
    /* @__PURE__ */ jsx("option", { value: "none", children: t("sound.none") }),
    files.length > 0 && /* @__PURE__ */ jsx("optgroup", { label: t("sound.myFiles"), children: files.map((f) => /* @__PURE__ */ jsx("option", { value: `file:${f.id}`, children: f.name }, f.id)) }),
    /* @__PURE__ */ jsx("optgroup", { label: t("sound.presets"), children: COMPLETION_SOUND_VARIANTS.map((v) => /* @__PURE__ */ jsx("option", { value: `preset:${v.id}`, children: v.name }, v.id)) })
  ] });
}
function SettingsPage() {
  const t = usePluginI18n(ID);
  const [cfg, setCfg] = useState(loadConfig);
  const [files, setFiles] = useState(loadFiles);
  const [error, setError] = useState("");
  const input = useRef(null);
  const update = (patch) => setCfg(saveConfig(patch));
  const addFile = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    setError("");
    if (!file) return;
    if (files.length >= MAX_FILES) return setError(t("files.tooMany", MAX_FILES));
    if (file.size > MAX_FILE_BYTES) return setError(t("files.tooBig", Math.round(MAX_FILE_BYTES / 1024)));
    try {
      const entry = { id: String(Date.now()), name: file.name, dataUrl: await readFile(file) };
      const next = [...files, entry];
      saveFiles(next);
      setFiles(next);
    } catch (err) {
      setError(t("files.saveFailed", String(err?.message || err)));
    }
  };
  const removeFile = (id) => {
    const next = files.filter((f) => f.id !== id);
    saveFiles(next);
    setFiles(next);
    const gone = `file:${id}`;
    const patch = {};
    if (cfg.sound === gone) patch.sound = DEFAULTS.sound;
    if (cfg.nightSound === gone) patch.nightSound = DEFAULTS.nightSound;
    if (Object.keys(patch).length) update(patch);
  };
  const preview = (sound) => /* @__PURE__ */ jsx(Button, { onClick: () => play(sound, cfg.volume), size: "sm", type: "button", variant: "outline", children: t("preview") });
  return /* @__PURE__ */ jsxs("div", { className: "flex flex-col gap-1", children: [
    /* @__PURE__ */ jsx(
      ListRow,
      {
        action: /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-2", children: [
          /* @__PURE__ */ jsx(SoundSelect, { files, onChange: (v) => update({ sound: v }), t, value: cfg.sound }),
          preview(cfg.sound)
        ] }),
        description: t("sound.description"),
        title: t("sound.title")
      }
    ),
    /* @__PURE__ */ jsx(
      ToggleRow,
      {
        checked: cfg.nightEnabled,
        description: t("night.description"),
        label: t("night.title"),
        onChange: (on) => update({ nightEnabled: on })
      }
    ),
    cfg.nightEnabled && /* @__PURE__ */ jsxs(Fragment, { children: [
      /* @__PURE__ */ jsx(
        ListRow,
        {
          action: /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-2", children: [
            /* @__PURE__ */ jsx("input", { className: control, onChange: (e) => update({ nightStart: e.target.value }), type: "time", value: cfg.nightStart }),
            /* @__PURE__ */ jsx("span", { children: "\u2013" }),
            /* @__PURE__ */ jsx("input", { className: control, onChange: (e) => update({ nightEnd: e.target.value }), type: "time", value: cfg.nightEnd })
          ] }),
          title: t("night.hours")
        }
      ),
      /* @__PURE__ */ jsx(
        ListRow,
        {
          action: /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-2", children: [
            /* @__PURE__ */ jsx(SoundSelect, { files, onChange: (v) => update({ nightSound: v }), t, value: cfg.nightSound }),
            preview(cfg.nightSound)
          ] }),
          title: t("night.sound")
        }
      )
    ] }),
    /* @__PURE__ */ jsx(
      ListRow,
      {
        action: /* @__PURE__ */ jsxs("div", { className: "flex flex-col items-end gap-2", children: [
          files.map((f) => /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-2 text-sm", children: [
            /* @__PURE__ */ jsx("span", { className: "max-w-64 truncate", children: f.name }),
            /* @__PURE__ */ jsx(Button, { onClick: () => removeFile(f.id), size: "sm", type: "button", variant: "outline", children: t("files.remove") })
          ] }, f.id)),
          /* @__PURE__ */ jsx("input", { accept: "audio/*", className: "hidden", onChange: addFile, ref: input, type: "file" }),
          /* @__PURE__ */ jsx(Button, { disabled: files.length >= MAX_FILES, onClick: () => input.current?.click(), size: "sm", type: "button", variant: "outline", children: t("files.add") })
        ] }),
        description: t("files.description", MAX_FILES, Math.round(MAX_FILE_BYTES / 1024)),
        title: t("files.title")
      }
    ),
    error && /* @__PURE__ */ jsx("p", { className: "px-1 text-sm text-destructive", children: error }),
    /* @__PURE__ */ jsx(
      ListRow,
      {
        action: /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-2", children: [
          /* @__PURE__ */ jsx("input", { max: "1", min: "0", onChange: (e) => update({ volume: Number(e.target.value) }), step: "0.05", type: "range", value: cfg.volume }),
          /* @__PURE__ */ jsxs("span", { className: "w-10 text-right text-sm", children: [
            Math.round(cfg.volume * 100),
            "%"
          ] })
        ] }),
        description: t("volume.description"),
        title: t("volume.title")
      }
    ),
    /* @__PURE__ */ jsx("p", { className: "px-1 pt-2 text-sm text-muted-foreground", children: t("note.builtin") })
  ] });
}
var plugin_default = {
  id: ID,
  name: "Completion Sound",
  description: "Pick the turn-completion sound: a Duckwork preset or your own audio file, with an optional night sound.",
  register(ctx2) {
    ctxRef = ctx2;
    ctx2.i18n?.register(messages_default);
    ctx2.onEvent("message.complete", (event) => {
      if (event?.replayed) return;
      const now = Date.now();
      if (now - lastPlayedAt < MIN_GAP_MS) return;
      lastPlayedAt = now;
      const cfg = loadConfig();
      play(soundNow(cfg), cfg.volume);
    });
    ctx2.registerSettingsPage?.({ id: "main", title: "Completion Sound", icon: "unmute", render: () => /* @__PURE__ */ jsx(SettingsPage, {}) });
  }
};
export {
  plugin_default as default
};
