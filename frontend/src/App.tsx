import { useCallback, useEffect, useState } from 'react'
import { api, setUnits, type Profile, type Prs } from './api'
import { ActualMaxChart } from './components/ActualMaxChart'
import { BodyweightPanel } from './components/BodyweightPanel'
import { E1rmChart } from './components/E1rmChart'
import { IntensityChart } from './components/IntensityChart'
import { Onboarding } from './components/Onboarding'
import { PrCards } from './components/PrCards'
import { PrTimeline } from './components/PrTimeline'
import { RepCurveChart } from './components/RepCurveChart'
import { SessionDrawer } from './components/SessionDrawer'
import { SettingsDrawer } from './components/SettingsDrawer'
import { SessionsTable } from './components/SessionsTable'
import { SyncBar } from './components/SyncBar'
import { TotalChart } from './components/TotalChart'
import { WeeklyVolumeChart } from './components/WeeklyVolumeChart'
import { useAsync } from './useAsync'
import { RangeBar, RangeProvider } from './range'

export default function App() {
  const [profile, setProfile] = useState<Profile | null>(null)
  const [error, setError] = useState<string>()
  const [settingsOpen, setSettingsOpen] = useState(false)

  useEffect(() => {
    api.profile().then(setProfile, (e) => setError(e instanceof Error ? e.message : String(e)))
  }, [])

  if (error) return <div className="app"><p className="error">Could not load profile: {error}</p></div>
  if (!profile) return <div className="app"><p className="muted">Loading…</p></div>
  // Module-level display unit, set before any child renders. Dashboard is keyed by it (and by
  // settings that change server-side results) so it remounts and refetches.
  setUnits(profile.units)
  if (!profile.onboarded) return <Onboarding initial={profile} onDone={setProfile} />

  return (
    <>
      <Dashboard key={`${profile.units}|${profile.dots_formula}|${profile.boostcamp.configured}|${JSON.stringify(profile.lift_map)}`} profile={profile} onSettings={() => setSettingsOpen(true)} />
      {settingsOpen && (
        <SettingsDrawer profile={profile} onChange={setProfile} onClose={() => setSettingsOpen(false)} />
      )}
    </>
  )
}

function Dashboard({ profile, onSettings }: { profile: Profile; onSettings: () => void }) {
  const [version, setVersion] = useState(0)
  const [openId, setOpenId] = useState<string | null>(null)
  const formula = profile.dots_formula
  const prs = useAsync<Prs>(() => api.prs(), [version])
  const close = useCallback(() => setOpenId(null), [])

  return (
    <RangeProvider>
    <div className="app">
      <header className="topbar">
        <h1>Weightroom{profile.name && <span className="muted small"> · {profile.name}</span>}</h1>
        <div className="topbar-right">
          <SyncBar version={version} onSynced={() => setVersion((v) => v + 1)} onSettings={onSettings} />
          <button className="btn ghost" onClick={onSettings}>Settings</button>
        </div>
      </header>

      <main>
        <RangeBar />
        {prs.error && <p className="error">Could not load data: {prs.error}</p>}
        {prs.data && <PrCards prs={prs.data} onOpen={setOpenId} />}

        <h2 className="section-title">Strength</h2>
        <div className="chart-grid">
          <E1rmChart version={version} onOpen={setOpenId} />
          <ActualMaxChart version={version} onOpen={setOpenId} />
          <RepCurveChart version={version} />
          <TotalChart version={version} formula={formula} onSettings={onSettings} />
        </div>

        <h2 className="section-title">Volume &amp; intensity</h2>
        <div className="chart-grid">
          <WeeklyVolumeChart version={version} />
          <IntensityChart version={version} />
        </div>

        <h2 className="section-title">PRs &amp; body</h2>
        <div className="chart-grid">
          <PrTimeline version={version} onOpen={setOpenId} />
          <BodyweightPanel version={version} onChanged={() => setVersion((v) => v + 1)} />
        </div>

        <h2 className="section-title">Sessions</h2>
        <SessionsTable version={version} onOpen={setOpenId} />
      </main>

      {openId && <SessionDrawer id={openId} onClose={close} />}
    </div>
    </RangeProvider>
  )
}
