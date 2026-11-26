import { useCallback, useState } from 'react'
import { api, type Prs } from './api'
import { ActualMaxChart } from './components/ActualMaxChart'
import { BodyweightPanel } from './components/BodyweightPanel'
import { E1rmChart } from './components/E1rmChart'
import { IntensityChart } from './components/IntensityChart'
import { PrCards } from './components/PrCards'
import { PrTimeline } from './components/PrTimeline'
import { RepCurveChart } from './components/RepCurveChart'
import { SessionDrawer } from './components/SessionDrawer'
import { SessionsTable } from './components/SessionsTable'
import { SyncBar } from './components/SyncBar'
import { TotalChart } from './components/TotalChart'
import { WeeklyVolumeChart } from './components/WeeklyVolumeChart'
import { useAsync } from './useAsync'
import { RangeBar, RangeProvider } from './range'

export default function App() {
  const [version, setVersion] = useState(0)
  const [openId, setOpenId] = useState<string | null>(null)
  const prs = useAsync<Prs>(() => api.prs(), [version])
  const close = useCallback(() => setOpenId(null), [])

  return (
    <RangeProvider>
    <div className="app">
      <header className="topbar">
        <h1>Weightroom</h1>
        <SyncBar version={version} onSynced={() => setVersion((v) => v + 1)} />
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
          <TotalChart version={version} />
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
