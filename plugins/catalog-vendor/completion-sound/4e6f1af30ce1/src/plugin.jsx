/**
 * Completion Sound — pick the sound Duckwork Desktop plays when a turn finishes: one of Duckwork' 14 built-in
 * presets or your own audio file, optionally with a different sound at night.
 *
 * Plugin SDK surface only: `ctx.onEvent('message.complete')`, `ctx.storage`, `ctx.i18n`,
 * `ctx.registerSettingsPage`. The presets are Duckwork' own synth code, vendored under src/vendor (MIT).
 * Duckwork' built-in completion sound cannot be switched off from a plugin, so it keeps playing until
 * Duckwork ships a "None" option; see README.
 */
import * as sdk from '@duckwork/plugin-sdk'
import { useRef, useState } from 'react'

import { COMPLETION_SOUND_VARIANTS, previewCompletionSound } from './vendor/completion-sound'
import messages from './messages'

const { Button, ListRow, ToggleRow, usePluginI18n } = sdk

const ID = 'completion-sound'
const MAX_FILES = 3
const MAX_FILE_BYTES = 1024 * 1024 // kept small: files live in the renderer's localStorage as data URLs
const MIN_GAP_MS = 1500 // one cue per burst when several chats finish in the same second
const DEFAULTS = {
  sound: 'preset:1',
  nightEnabled: false,
  nightSound: 'preset:3',
  nightStart: '22:00',
  nightEnd: '07:00',
  volume: 0.8
}

let ctxRef = null
let lastPlayedAt = 0

const loadConfig = () => ({ ...DEFAULTS, ...ctxRef.storage.get('config', {}) })
const saveConfig = patch => {
  const next = { ...loadConfig(), ...patch }
  ctxRef.storage.set('config', next)
  return next
}
const loadFiles = () => ctxRef.storage.get('files', [])
const saveFiles = files => ctxRef.storage.set('files', files)

function minutes(hhmm) {
  const [h, m] = String(hhmm).split(':').map(Number)
  return (Number.isFinite(h) ? h : 0) * 60 + (Number.isFinite(m) ? m : 0)
}

function isNight(cfg, now = new Date()) {
  if (!cfg.nightEnabled) return false
  const t = now.getHours() * 60 + now.getMinutes()
  const a = minutes(cfg.nightStart)
  const b = minutes(cfg.nightEnd)
  return a <= b ? t >= a && t < b : t >= a || t < b // the window may cross midnight
}

const soundNow = cfg => (isNight(cfg) ? cfg.nightSound : cfg.sound)

function play(sound, volume) {
  if (!sound || sound === 'none') return
  const sep = sound.indexOf(':')
  const kind = sound.slice(0, sep)
  const id = sound.slice(sep + 1)
  if (kind === 'preset') {
    previewCompletionSound(Number(id))
    return
  }
  if (kind === 'file') {
    const file = loadFiles().find(f => f.id === id)
    if (!file) return
    const audio = new Audio(file.dataUrl)
    audio.volume = Math.max(0, Math.min(1, Number(volume) || 0))
    audio.play().catch(err => console.warn('[completion-sound] playback failed', err))
  }
}

function readFile(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(file)
  })
}

const control = 'rounded-md border border-border bg-transparent px-2 py-1 text-sm'

function SoundSelect({ files, onChange, t, value }) {
  return (
    <select className={`min-w-56 ${control}`} onChange={e => onChange(e.target.value)} value={value}>
      <option value="none">{t('sound.none')}</option>
      {files.length > 0 && (
        <optgroup label={t('sound.myFiles')}>
          {files.map(f => (
            <option key={f.id} value={`file:${f.id}`}>
              {f.name}
            </option>
          ))}
        </optgroup>
      )}
      <optgroup label={t('sound.presets')}>
        {COMPLETION_SOUND_VARIANTS.map(v => (
          <option key={v.id} value={`preset:${v.id}`}>
            {v.name}
          </option>
        ))}
      </optgroup>
    </select>
  )
}

function SettingsPage() {
  const t = usePluginI18n(ID)
  const [cfg, setCfg] = useState(loadConfig)
  const [files, setFiles] = useState(loadFiles)
  const [error, setError] = useState('')
  const input = useRef(null)
  const update = patch => setCfg(saveConfig(patch))

  const addFile = async event => {
    const file = event.target.files?.[0]
    event.target.value = ''
    setError('')
    if (!file) return
    if (files.length >= MAX_FILES) return setError(t('files.tooMany', MAX_FILES))
    if (file.size > MAX_FILE_BYTES) return setError(t('files.tooBig', Math.round(MAX_FILE_BYTES / 1024)))
    try {
      const entry = { id: String(Date.now()), name: file.name, dataUrl: await readFile(file) }
      const next = [...files, entry]
      saveFiles(next)
      setFiles(next)
    } catch (err) {
      setError(t('files.saveFailed', String(err?.message || err)))
    }
  }

  const removeFile = id => {
    const next = files.filter(f => f.id !== id)
    saveFiles(next)
    setFiles(next)
    const gone = `file:${id}`
    const patch = {}
    if (cfg.sound === gone) patch.sound = DEFAULTS.sound
    if (cfg.nightSound === gone) patch.nightSound = DEFAULTS.nightSound
    if (Object.keys(patch).length) update(patch)
  }

  const preview = sound => (
    <Button onClick={() => play(sound, cfg.volume)} size="sm" type="button" variant="outline">
      {t('preview')}
    </Button>
  )

  return (
    <div className="flex flex-col gap-1">
      <ListRow
        action={
          <div className="flex items-center gap-2">
            <SoundSelect files={files} onChange={v => update({ sound: v })} t={t} value={cfg.sound} />
            {preview(cfg.sound)}
          </div>
        }
        description={t('sound.description')}
        title={t('sound.title')}
      />
      <ToggleRow
        checked={cfg.nightEnabled}
        description={t('night.description')}
        label={t('night.title')}
        onChange={on => update({ nightEnabled: on })}
      />
      {cfg.nightEnabled && (
        <>
          <ListRow
            action={
              <div className="flex items-center gap-2">
                <input className={control} onChange={e => update({ nightStart: e.target.value })} type="time" value={cfg.nightStart} />
                <span>–</span>
                <input className={control} onChange={e => update({ nightEnd: e.target.value })} type="time" value={cfg.nightEnd} />
              </div>
            }
            title={t('night.hours')}
          />
          <ListRow
            action={
              <div className="flex items-center gap-2">
                <SoundSelect files={files} onChange={v => update({ nightSound: v })} t={t} value={cfg.nightSound} />
                {preview(cfg.nightSound)}
              </div>
            }
            title={t('night.sound')}
          />
        </>
      )}
      <ListRow
        action={
          <div className="flex flex-col items-end gap-2">
            {files.map(f => (
              <div className="flex items-center gap-2 text-sm" key={f.id}>
                <span className="max-w-64 truncate">{f.name}</span>
                <Button onClick={() => removeFile(f.id)} size="sm" type="button" variant="outline">
                  {t('files.remove')}
                </Button>
              </div>
            ))}
            <input accept="audio/*" className="hidden" onChange={addFile} ref={input} type="file" />
            <Button disabled={files.length >= MAX_FILES} onClick={() => input.current?.click()} size="sm" type="button" variant="outline">
              {t('files.add')}
            </Button>
          </div>
        }
        description={t('files.description', MAX_FILES, Math.round(MAX_FILE_BYTES / 1024))}
        title={t('files.title')}
      />
      {error && <p className="px-1 text-sm text-destructive">{error}</p>}
      <ListRow
        action={
          <div className="flex items-center gap-2">
            <input max="1" min="0" onChange={e => update({ volume: Number(e.target.value) })} step="0.05" type="range" value={cfg.volume} />
            <span className="w-10 text-right text-sm">{Math.round(cfg.volume * 100)}%</span>
          </div>
        }
        description={t('volume.description')}
        title={t('volume.title')}
      />
      <p className="px-1 pt-2 text-sm text-muted-foreground">{t('note.builtin')}</p>
    </div>
  )
}

export default {
  id: ID,
  name: 'Completion Sound',
  description: 'Pick the turn-completion sound: a Duckwork preset or your own audio file, with an optional night sound.',
  register(ctx) {
    ctxRef = ctx
    ctx.i18n?.register(messages)

    ctx.onEvent('message.complete', event => {
      if (event?.replayed) return // reconnect replays are not fresh turns
      const now = Date.now()
      if (now - lastPlayedAt < MIN_GAP_MS) return
      lastPlayedAt = now
      const cfg = loadConfig()
      play(soundNow(cfg), cfg.volume)
    })

    ctx.registerSettingsPage?.({ id: 'main', title: 'Completion Sound', icon: 'unmute', render: () => <SettingsPage /> })
  }
}
