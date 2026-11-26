import { useEffect, useState } from 'react'
import { api, LB_PER_KG, type ExerciseName, type LiftMap, type Profile, type ProfileSex, type Sex, type Units } from '../api'
import {
  BoostcampForm, Field, LiftMapEditor, SexFields, SyncIntervalField, UnitsField,
} from './ProfileFields'
import { CURRENT_YEAR, errMsg, parseWeight, todayIso } from '../profileUtils'

const STEPS = ['About you', 'Body', 'Boostcamp', 'Lifts'] as const
const LEGACY_SEX_KEY = 'weightroom.sex'

export function Onboarding({ initial, onDone }: { initial: Profile; onDone: (p: Profile) => void }) {
  const [step, setStep] = useState(0)
  const [profile, setProfile] = useState(initial)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string>()

  // Step 1
  const [name, setName] = useState(initial.name ?? '')
  const legacy = localStorage.getItem(LEGACY_SEX_KEY)
  const [sex, setSex] = useState<ProfileSex | null>(initial.sex ?? (legacy === 'f' || legacy === 'm' ? legacy : null))
  const [formula, setFormula] = useState<Sex>(initial.dots_formula)
  const [birthYear, setBirthYear] = useState(initial.birth_year?.toString() ?? '')
  const [height, setHeight] = useState(initial.height_cm?.toString() ?? '')
  // Step 2
  const [units, setUnits] = useState<Units>(initial.units)
  const [bw, setBw] = useState('')
  const [bwDate, setBwDate] = useState(todayIso)
  const [start, setStart] = useState(initial.training_start ?? '')
  // Step 3
  const [syncHours, setSyncHours] = useState(initial.sync_interval_hours)
  const [syncMsg, setSyncMsg] = useState<string>()
  // Step 4
  const [liftMap, setLiftMap] = useState<LiftMap>(initial.lift_map)
  const [exercises, setExercises] = useState<ExerciseName[]>([])

  useEffect(() => {
    if (step === 3) api.exercises().then(setExercises, () => setExercises([]))
  }, [step])

  const year = CURRENT_YEAR
  const bwKg = parseWeight(bw, units)
  const heightCm = height ? Number(height) : null
  const by = birthYear ? Number(birthYear) : null
  const stepValid = [
    sex != null && (heightCm == null || (heightCm >= 100 && heightCm <= 250)) && (by == null || (by >= 1900 && by <= year)),
    bw.trim() === '' || bwKg != null,
    true,
    true,
  ][step]

  const payload = () => {
    switch (step) {
      case 0:
        return {
          name: name.trim() || null, sex: sex!, dots_formula: sex === 'other' ? formula : (sex as Sex),
          birth_year: by, height_cm: heightCm,
        }
      case 1:
        return { units, training_start: start || null, ...(bwKg != null ? { bodyweight: { date: bwDate, kg: bwKg } } : {}) }
      case 2:
        return { sync_interval_hours: syncHours }
      default:
        return { lift_map: liftMap, complete: true }
    }
  }

  const next = async () => {
    setBusy(true)
    setErr(undefined)
    try {
      const p = await api.updateProfile(payload())
      setProfile(p)
      if (step === 0) localStorage.removeItem(LEGACY_SEX_KEY)
      if (step === STEPS.length - 1) onDone(p)
      else setStep(step + 1)
    } catch (e) {
      setErr(errMsg(e))
    } finally {
      setBusy(false)
    }
  }

  const connected = async (p: Profile) => {
    setProfile(p)
    if (!p.boostcamp.configured) return
    setSyncMsg('Connected. Importing your history…')
    try {
      const row = await api.sync()
      setSyncMsg(row.ok ? `Imported ${row.sessions_seen ?? 0} sessions.` : `Sync failed: ${row.error}`)
    } catch (e) {
      setSyncMsg(`Sync failed: ${errMsg(e)}`)
    }
  }

  return (
    <div className="onboarding">
      <div className="card onboarding-card">
        <header>
          <h1>Welcome to Weightroom</h1>
          <p className="muted">A few questions to set things up. You can change all of this later in Settings.</p>
          <ol className="steps">
            {STEPS.map((s, i) => (
              <li key={s} className={i === step ? 'on' : i < step ? 'done' : ''}>{s}</li>
            ))}
          </ol>
        </header>

        {step === 0 && (
          <div className="stack">
            <Field label="Name (optional)">
              <input value={name} maxLength={60} onChange={(e) => setName(e.target.value)} autoFocus />
            </Field>
            <SexFields sex={sex} formula={formula} onSex={setSex} onFormula={setFormula} />
            <div className="row">
              <Field label="Birth year (optional)">
                <input type="number" min={1900} max={year} value={birthYear} onChange={(e) => setBirthYear(e.target.value)} />
              </Field>
              <Field label="Height in cm (optional)">
                <input type="number" min={100} max={250} step="0.5" value={height} onChange={(e) => setHeight(e.target.value)} />
              </Field>
            </div>
          </div>
        )}

        {step === 1 && (
          <div className="stack">
            <UnitsField units={units} onChange={setUnits} />
            <div className="row">
              <Field label={`Bodyweight (${units})`} hint="Used for DOTS. You can log more entries on the dashboard.">
                <input type="number" step="0.1" value={bw} onChange={(e) => setBw(e.target.value)}
                  placeholder={units === 'lb' ? String(Math.round(80 * LB_PER_KG)) : '80'} />
              </Field>
              <Field label="Weighed on">
                <input type="date" value={bwDate} max={todayIso()} onChange={(e) => setBwDate(e.target.value)} />
              </Field>
            </div>
            {bw.trim() !== '' && bwKg == null && <p className="error">Enter a bodyweight between 20 and 400 kg.</p>}
            <Field label="Started training on (optional)" hint="Shown on your profile, for context on your progress.">
              <input type="date" value={start} max={todayIso()} onChange={(e) => setStart(e.target.value)} />
            </Field>
          </div>
        )}

        {step === 2 && (
          <div className="stack">
            <p>
              Connect your Boostcamp account to import your workouts. This step is optional: you can skip it and
              connect later from Settings.
            </p>
            <BoostcampForm profile={profile} onSaved={connected} />
            {syncMsg && <p className="muted">{syncMsg}</p>}
            <SyncIntervalField hours={syncHours} onChange={setSyncHours} />
          </div>
        )}

        {step === 3 && (
          <LiftMapEditor value={liftMap} exercises={exercises} onChange={setLiftMap} />
        )}

        {err && <p className="error">{err}</p>}
        <footer className="onboarding-nav">
          <button className="btn ghost" onClick={() => setStep(step - 1)} disabled={step === 0 || busy}>Back</button>
          <button className="btn" onClick={next} disabled={!stepValid || busy}>
            {step === STEPS.length - 1 ? 'Finish' : step === 2 && !profile.boostcamp.configured ? 'Skip for now' : 'Next'}
          </button>
        </footer>
      </div>
    </div>
  )
}
