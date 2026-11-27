export type Lift = 'squat' | 'bench' | 'deadlift'
export const LIFTS: Lift[] = ['squat', 'bench', 'deadlift']
export const LIFT_LABEL: Record<Lift, string> = { squat: 'Squat', bench: 'Bench', deadlift: 'Deadlift' }

export interface SetRef {
  session_id: string
  date: string
  title: string | null
  exercise: string
  weight_kg: number
  reps: number
  volume_kg: number
  e1rm_kg: number | null
}

export interface SessionVolumeRef {
  session_id: string
  date: string
  title: string | null
  volume_kg: number
  sets: number
  reps: number
}

export interface LiftPrs {
  heaviest: SetRef | null
  best_e1rm: SetRef | null
  best_set_volume: SetRef | null
  best_session_volume: SessionVolumeRef | null
  rep_maxes: Record<string, SetRef | null>
  estimated_1rm: EstimatePoint | null
  days_since_pr: number | null
}
export type Prs = Record<Lift, LiftPrs>

export interface EstimatePoint {
  date: string
  e1rm_kg: number
}
export interface LiftEstimate {
  current: EstimatePoint | null
  series: EstimatePoint[]
}
export interface ActualMax extends SetRef {
  is_pr: boolean
  running_best_kg: number
}
export interface RepCurvePoint {
  reps: number
  all: number | null
  d90: number | null
  d30: number | null
}
export const ZONES = ['<70', '70-80', '80-90', '90+'] as const
export type Zone = (typeof ZONES)[number]
export type IntensityWeek = { week_start: string } & Record<Zone, number>
export interface PrEvent extends SetRef {
  lift: Lift
  kind: string
  value: number
  previous: number | null
}
export interface PrTimeline {
  events: PrEvent[]
  last_pr_date: Record<Lift, string | null>
  days_since: Record<Lift, number | null>
}
type LiftTotals = Record<Lift, number | null> & { total: number | null }
export interface TotalPoint {
  date: string
  estimated: LiftTotals
  actual: LiftTotals
  bodyweight_kg: number | null
  dots_estimated: number | null
  dots_actual: number | null
}
export interface BodyweightEntry {
  date: string
  kg: number
}
export type Sex = 'm' | 'f'
export type ProfileSex = Sex | 'other'
export type Units = 'kg' | 'lb'
export type LiftMap = Record<Lift, string[]>

export interface Profile {
  name: string | null
  sex: ProfileSex | null
  dots_formula: Sex
  units: Units
  height_cm: number | null
  birth_year: number | null
  training_start: string | null
  sync_interval_hours: number
  onboarded_at: string | null
  onboarded: boolean
  lift_map: LiftMap
  boostcamp: {
    configured: boolean
    source: 'env' | 'db' | null
    token_hint: string | null
    decrypt_error: boolean
  }
}

export interface ProfileUpdate {
  name?: string | null
  sex?: ProfileSex
  dots_formula?: Sex
  units?: Units
  height_cm?: number | null
  birth_year?: number | null
  training_start?: string | null
  sync_interval_hours?: number
  lift_map?: LiftMap
  bodyweight?: { date: string; kg: number }
  complete?: boolean
}

export interface ExerciseName {
  exercise: string
  lift: Lift | null
  sets: number
  last_date: string
}

export interface SessionSummary {
  id: string
  date: string
  finished_at: string
  title: string | null
  program: string | null
  volume_kg: number
  sets: number
  reps: number
  exercises: string[]
}

export interface SessionPage {
  total: number
  limit: number
  offset: number
  items: SessionSummary[]
}

export interface SessionDetail extends Omit<SessionSummary, 'exercises'> {
  exercises: {
    exercise: string
    lift: Lift | null
    volume_kg: number
    best_e1rm_kg: number | null
    sets: { set_idx: number; weight_kg: number; reps: number; volume_kg: number; e1rm_kg: number | null }[]
  }[]
}

export interface WeekVolume {
  iso_year: number
  iso_week: number
  week_start: string
  sessions: number
  squat: number
  bench: number
  deadlift: number
  other: number
  total: number
}

export interface LiftHistoryPoint {
  session_id: string
  date: string
  title: string | null
  best_e1rm_kg: number | null
  top_set: { weight_kg: number; reps: number; exercise: string } | null
  volume_kg: number
  sets: number
}

export interface SyncRow {
  id: number
  started_at: string
  finished_at: string | null
  ok: number
  sessions_seen: number | null
  error: string | null
  last_success_at?: string | null
}

export interface SyncStatus {
  last: SyncRow | null
  configured: boolean
  interval_hours: number
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init)
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      if (body?.detail) detail = String(body.detail)
    } catch {
      /* not json */
    }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export const api = {
  prs: () => request<Prs>('/api/prs'),
  sessions: (limit: number, offset: number) =>
    request<SessionPage>(`/api/sessions?limit=${limit}&offset=${offset}`),
  session: (id: string) => request<SessionDetail>(`/api/sessions/${encodeURIComponent(id)}`),
  weekly: (weeks: number) => request<WeekVolume[]>(`/api/volume/weekly?weeks=${weeks}`),
  liftHistory: (lift: Lift) => request<LiftHistoryPoint[]>(`/api/lifts/${lift}/history`),
  estimate: (lift: Lift) => request<LiftEstimate>(`/api/lifts/${lift}/estimate`),
  actualMaxes: (lift: Lift) => request<ActualMax[]>(`/api/lifts/${lift}/actual-maxes`),
  repCurve: (lift: Lift) => request<RepCurvePoint[]>(`/api/lifts/${lift}/rep-curve`),
  intensity: (weeks: number, lift?: Lift) =>
    request<IntensityWeek[]>(`/api/intensity?weeks=${weeks}${lift ? `&lift=${lift}` : ''}`),
  prTimeline: () => request<PrTimeline>('/api/prs/timeline'),
  total: () => request<TotalPoint[]>('/api/total'),
  bodyweight: () => request<BodyweightEntry[]>('/api/bodyweight'),
  addBodyweight: (date: string, kg: number) =>
    request<BodyweightEntry[]>('/api/bodyweight', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ date, kg }),
    }),
  deleteBodyweight: (date: string) => request<BodyweightEntry[]>(`/api/bodyweight/${date}`, { method: 'DELETE' }),
  sync: () => request<SyncRow>('/api/sync', { method: 'POST' }),
  syncStatus: () => request<SyncStatus>('/api/sync/status'),
  profile: () => request<Profile>('/api/profile'),
  updateProfile: (body: ProfileUpdate) =>
    request<Profile>('/api/profile', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  exercises: () => request<ExerciseName[]>('/api/exercises'),
  setCredentials: (refresh_token: string, api_key: string) =>
    request<Profile>('/api/boostcamp/credentials', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token, api_key }),
    }),
  clearCredentials: () => request<Profile>('/api/boostcamp/credentials', { method: 'DELETE' }),
}

// --- Display units ----------------------------------------------------------
// The backend always speaks kg. The UI converts at the edges. App sets the unit
// from the profile and remounts the dashboard when it changes.
export const LB_PER_KG = 2.20462
let UNITS: Units = 'kg'
export const setUnits = (u: Units) => {
  UNITS = u
}
export const unit = () => UNITS
/** kg -> display unit. */
export const w = (kgVal: number) => (UNITS === 'lb' ? kgVal * LB_PER_KG : kgVal)
/** kg -> display unit, rounded to 0.1. */
export const wr = (kgVal: number) => Math.round(w(kgVal) * 10) / 10
/** display unit -> kg. */
export const toKg = (v: number) => (UNITS === 'lb' ? v / LB_PER_KG : v)

const kgFmt = new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 })
const bigFmt = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 })

/** Format a kg value in the user's display unit. */
export const kg = (n: number | null | undefined) => (n == null ? '–' : `${kgFmt.format(w(n))} ${UNITS}`)
export const bigKg = (n: number | null | undefined) => (n == null ? '–' : `${bigFmt.format(w(n))} ${UNITS}`)
/** Format a value that is already in display units. */
export const du = (n: number | null | undefined) => (n == null ? '–' : `${kgFmt.format(n)} ${UNITS}`)
export const bigDu = (n: number | null | undefined) => (n == null ? '–' : `${bigFmt.format(n)} ${UNITS}`)

/** ISO date string → ms timestamp at local midnight. */
export const ts = (iso: string) => new Date(`${iso.slice(0, 10)}T00:00:00`).getTime()
export const tooltipStyle = { background: 'var(--panel-2)', border: '1px solid var(--border)', borderRadius: 8 }

export function fmtDate(iso: string): string {
  return new Date(`${iso.slice(0, 10)}T00:00:00`).toLocaleDateString(undefined, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

/** sync_log times are UTC ISO strings from the backend. */
export function fmtRelative(iso: string | null | undefined): string {
  if (!iso) return 'never'
  const then = new Date(iso).getTime()
  const mins = Math.round((Date.now() - then) / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins} min ago`
  const hours = Math.round(mins / 60)
  if (hours < 48) return `${hours} h ago`
  return new Date(iso).toLocaleString()
}
