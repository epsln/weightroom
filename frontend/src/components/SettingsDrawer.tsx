import { useEffect, useState } from 'react'
import { api, type ExerciseName, type LiftMap, type Profile, type ProfileSex, type Sex, type Units } from '../api'
import { useAsync } from '../useAsync'
import {
  BoostcampForm, Field, LiftMapEditor, SexFields, SyncIntervalField, UnitsField,
} from './ProfileFields'
import { CURRENT_YEAR, errMsg, todayIso } from '../profileUtils'

export function SettingsDrawer({ profile, onChange, onClose }: {
  profile: Profile
  onChange: (p: Profile) => void
  onClose: () => void
}) {
  const [name, setName] = useState(profile.name ?? '')
  const [sex, setSex] = useState<ProfileSex | null>(profile.sex)
  const [formula, setFormula] = useState<Sex>(profile.dots_formula)
  const [birthYear, setBirthYear] = useState(profile.birth_year?.toString() ?? '')
  const [height, setHeight] = useState(profile.height_cm?.toString() ?? '')
  const [units, setUnits] = useState<Units>(profile.units)
  const [start, setStart] = useState(profile.training_start ?? '')
  const [syncHours, setSyncHours] = useState(profile.sync_interval_hours)
  const [liftMap, setLiftMap] = useState<LiftMap>(profile.lift_map)
  const exercises = useAsync<ExerciseName[]>(() => api.exercises(), [])
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<string>()
  const [err, setErr] = useState<string>()

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const year = CURRENT_YEAR
  const by = birthYear ? Number(birthYear) : null
  const heightCm = height ? Number(height) : null

  const save = async () => {
    setBusy(true)
    setErr(undefined)
    setMsg(undefined)
    try {
      const p = await api.updateProfile({
        name: name.trim() || null,
        ...(sex ? { sex, dots_formula: sex === 'other' ? formula : (sex as Sex) } : {}),
        birth_year: by, height_cm: heightCm, units, training_start: start || null,
        sync_interval_hours: syncHours, lift_map: liftMap,
      })
      onChange(p)
      setMsg('Saved.')
    } catch (e) {
      setErr(errMsg(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside className="drawer" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <header className="drawer-head">
          <div>
            <h2>Settings</h2>
            {profile.onboarded_at && (
              <div className="muted small">Set up on {new Date(profile.onboarded_at).toLocaleDateString()}</div>
            )}
          </div>
          <button className="btn ghost" onClick={onClose} aria-label="Close">✕</button>
        </header>

        <div className="stack">
          <h3 className="section-title">Profile</h3>
          <Field label="Name">
            <input value={name} maxLength={60} onChange={(e) => setName(e.target.value)} />
          </Field>
          <SexFields sex={sex} formula={formula} onSex={setSex} onFormula={setFormula} />
          <div className="row">
            <Field label="Birth year" hint={by ? `About ${year - by} years old` : undefined}>
              <input type="number" min={1900} max={year} value={birthYear} onChange={(e) => setBirthYear(e.target.value)} />
            </Field>
            <Field label="Height (cm)">
              <input type="number" min={100} max={250} step="0.5" value={height} onChange={(e) => setHeight(e.target.value)} />
            </Field>
          </div>
          <Field label="Started training on">
            <input type="date" value={start} max={todayIso()} onChange={(e) => setStart(e.target.value)} />
          </Field>
          <UnitsField units={units} onChange={setUnits} />

          <h3 className="section-title">Sync</h3>
          <SyncIntervalField hours={syncHours} onChange={setSyncHours} />

          <h3 className="section-title">Lift mapping</h3>
          <LiftMapEditor value={liftMap} exercises={exercises.data ?? []} onChange={setLiftMap} />

          {err && <p className="error">{err}</p>}
          {msg && <p className="muted">{msg}</p>}
          <div>
            <button className="btn" onClick={save} disabled={busy || sex == null}>{busy ? 'Saving…' : 'Save settings'}</button>
          </div>

          <h3 className="section-title">Boostcamp</h3>
          <BoostcampForm profile={profile} onSaved={onChange} />
        </div>
      </aside>
    </div>
  )
}
