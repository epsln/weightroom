import { useState } from 'react'
import {
  api, LIFT_LABEL, LIFTS,
  type ExerciseName, type Lift, type LiftMap, type Profile, type ProfileSex, type Sex, type Units,
} from '../api'
import { errMsg, insecureOrigin } from '../profileUtils'
import { LIFT_COLOR } from '../colors'

export function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
      {hint && <span className="muted small">{hint}</span>}
    </label>
  )
}

export function Choice<T extends string>({ value, options, onChange }: {
  value: T | null
  options: { value: T; label: string }[]
  onChange: (v: T) => void
}) {
  return (
    <div className="toggles">
      {options.map((o) => (
        <button type="button" key={o.value} className={`chip ${value === o.value ? 'on' : ''}`}
          onClick={() => onChange(o.value)}>
          {o.label}
        </button>
      ))}
    </div>
  )
}

export function SexFields({ sex, formula, onSex, onFormula }: {
  sex: ProfileSex | null
  formula: Sex
  onSex: (s: ProfileSex) => void
  onFormula: (f: Sex) => void
}) {
  return (
    <>
      <Field label="Sex" hint="Used to pick the DOTS formula for your strength score.">
        <Choice value={sex} onChange={onSex}
          options={[{ value: 'm', label: 'Man' }, { value: 'f', label: 'Woman' }, { value: 'other', label: 'Other' }]} />
      </Field>
      {sex === 'other' && (
        <Field label="DOTS formula" hint="DOTS only has male and female coefficients. Pick the one you want to be scored with.">
          <Choice value={formula} onChange={onFormula}
            options={[{ value: 'm', label: 'Male formula' }, { value: 'f', label: 'Female formula' }]} />
        </Field>
      )}
    </>
  )
}

export function UnitsField({ units, onChange }: { units: Units; onChange: (u: Units) => void }) {
  return (
    <Field label="Units" hint="Display only. Data is stored in kg.">
      <Choice value={units} onChange={onChange}
        options={[{ value: 'kg', label: 'Kilograms (kg)' }, { value: 'lb', label: 'Pounds (lb)' }]} />
    </Field>
  )
}

export function BoostcampHelp() {
  return (
    <details className="help">
      <summary>Where do I find these?</summary>
      <ol>
        <li>Log in to <a href="https://www.boostcamp.app" target="_blank" rel="noreferrer">boostcamp.app</a> in a desktop browser.</li>
        <li>Open DevTools (F12) → <b>Application</b> → <b>IndexedDB</b> → <code>firebaseLocalStorageDb</code> → <code>firebaseLocalStorage</code>.</li>
        <li>Expand the single entry and copy:
          <ul>
            <li><code>value.stsTokenManager.refreshToken</code> → Refresh token</li>
            <li><code>value.apiKey</code> → API key</li>
          </ul>
        </li>
      </ol>
    </details>
  )
}

/** Paste-and-verify form. Calls onSaved with the updated profile once Boostcamp accepted the credentials. */
export function BoostcampForm({ profile, onSaved }: { profile: Profile; onSaved: (p: Profile) => void }) {
  const [token, setToken] = useState('')
  const [key, setKey] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string>()
  const bc = profile.boostcamp

  if (bc.source === 'env') {
    return <p className="muted">Connected using credentials from the server environment (<code>.env</code>).</p>
  }

  const save = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setErr(undefined)
    try {
      const p = await api.setCredentials(token, key)
      setToken('')
      setKey('')
      onSaved(p)
    } catch (ex) {
      setErr(errMsg(ex))
    } finally {
      setBusy(false)
    }
  }
  const disconnect = async () => {
    setBusy(true)
    try {
      onSaved(await api.clearCredentials())
    } catch (ex) {
      setErr(errMsg(ex))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="stack" onSubmit={save}>
      {bc.configured && (
        <p>
          <span className="badge ok">connected</span> token {bc.token_hint}{' '}
          <button type="button" className="link" onClick={disconnect} disabled={busy}>disconnect</button>
        </p>
      )}
      {bc.decrypt_error && (
        <p className="error">The stored credentials can't be decrypted (the encryption key changed). Paste them again.</p>
      )}
      {insecureOrigin() && (
        <p className="warn-box">
          This page is served over plain HTTP. The token would cross the network unencrypted. Use HTTPS or
          open Weightroom from the server itself.
        </p>
      )}
      <BoostcampHelp />
      <Field label="Refresh token">
        <input type="password" autoComplete="off" spellCheck={false} value={token}
          onChange={(e) => setToken(e.target.value)} placeholder={bc.configured ? 'Paste to replace' : 'AMf-…'} />
      </Field>
      <Field label="API key">
        <input type="password" autoComplete="off" spellCheck={false} value={key}
          onChange={(e) => setKey(e.target.value)} placeholder="AIza…" />
      </Field>
      <p className="muted small">
        Checked with Boostcamp before saving, then stored encrypted on this server. It is never sent back to the browser.
      </p>
      {err && <p className="error">{err}</p>}
      <div>
        <button className="btn" type="submit" disabled={busy || !token.trim() || !key.trim()}>
          {busy ? 'Checking…' : bc.configured ? 'Replace credentials' : 'Connect'}
        </button>
      </div>
    </form>
  )
}

export function SyncIntervalField({ hours, onChange }: { hours: number; onChange: (h: number) => void }) {
  return (
    <Field label="Sync every" hint="How often Weightroom pulls new workouts from Boostcamp.">
      <Choice value={String(hours)} onChange={(v) => onChange(Number(v))}
        options={[1, 3, 6, 12, 24].map((h) => ({ value: String(h), label: `${h} h` }))} />
    </Field>
  )
}

/** Checkbox grid: which Boostcamp exercise names count as squat / bench / deadlift. */
export function LiftMapEditor({ value, exercises, onChange }: {
  value: LiftMap
  exercises: ExerciseName[]
  onChange: (m: LiftMap) => void
}) {
  const names = [...new Set([...exercises.map((e) => e.exercise), ...LIFTS.flatMap((l) => value[l])])]
  const sets = new Map(exercises.map((e) => [e.exercise, e.sets]))
  const [filter, setFilter] = useState('')
  const shown = names
    .filter((n) => n.toLowerCase().includes(filter.toLowerCase()))
    .sort((a, b) => (sets.get(b) ?? 0) - (sets.get(a) ?? 0))
  const liftOf = (n: string) => LIFTS.find((l) => value[l].includes(n)) ?? null
  const assign = (n: string, lift: Lift | null) => {
    const next = Object.fromEntries(LIFTS.map((l) => [l, value[l].filter((x) => x !== n)])) as LiftMap
    if (lift) next[lift] = [...next[lift], n]
    onChange(next)
  }

  return (
    <div className="stack">
      <p className="muted small">
        Pick the exact Boostcamp exercises that count as your competition lifts. Variations you leave
        unassigned still count toward volume.
      </p>
      {names.length > 8 && <input placeholder="Filter exercises…" value={filter} onChange={(e) => setFilter(e.target.value)} />}
      <div className="liftmap">
        {shown.map((n) => (
          <div key={n} className="liftmap-row">
            <span>
              {n} {sets.has(n) ? <span className="muted small">· {sets.get(n)} sets</span> : <span className="muted small">· not in history yet</span>}
            </span>
            <div className="toggles">
              {LIFTS.map((l) => (
                <button type="button" key={l} className={`chip ${liftOf(n) === l ? 'on' : ''}`}
                  style={{ '--c': LIFT_COLOR[l] } as React.CSSProperties}
                  onClick={() => assign(n, liftOf(n) === l ? null : l)}>
                  {LIFT_LABEL[l]}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
