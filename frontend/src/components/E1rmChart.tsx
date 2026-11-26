import { useState } from 'react'
import {
  CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis,
} from 'recharts'
import { api, du, fmtDate, kg, unit, wr, LIFT_LABEL, LIFTS, shortDate, tooltipStyle, ts, type Lift } from '../api'
import { useAsync } from '../useAsync'
import { LIFT_COLOR } from '../colors'
import { DragZoom, useRange } from '../range'
import { within, xDomain } from '../rangeUtils'

interface Pt {
  t: number
  v: number
  session_id?: string
  note?: string
}

interface LiftData {
  estimate: Pt[]
  sessions: Pt[]
  singles: Pt[]
}

async function load(): Promise<Record<Lift, LiftData>> {
  const out = {} as Record<Lift, LiftData>
  await Promise.all(
    LIFTS.map(async (l) => {
      const [est, hist, singles] = await Promise.all([api.estimate(l), api.liftHistory(l), api.actualMaxes(l)])
      out[l] = {
        estimate: est.series.map((p) => ({ t: ts(p.date), v: wr(p.e1rm_kg), note: 'rolling estimate' })),
        sessions: hist
          .filter((h) => h.best_e1rm_kg != null)
          .map((h) => ({
            t: ts(h.date), v: wr(h.best_e1rm_kg!), session_id: h.session_id,
            note: h.top_set ? `best set e1RM · top ${kg(h.top_set.weight_kg)} × ${h.top_set.reps}` : 'best set e1RM',
          })),
        singles: singles.map((s) => ({
          t: ts(s.date), v: wr(s.weight_kg), session_id: s.session_id, note: s.is_pr ? 'actual single · PR' : 'actual single',
        })),
      }
    }),
  )
  return out
}

const openFrom = (onOpen: (id: string) => void) => (p: unknown) => {
  const id = (p as { payload?: Pt }).payload?.session_id
  if (id) onOpen(id)
}

export function E1rmChart({ version, onOpen }: { version: number; onOpen: (id: string) => void }) {
  const [shown, setShown] = useState<Record<Lift, boolean>>({ squat: true, bench: true, deadlift: true })
  const [showSessions, setShowSessions] = useState(true)
  const res = useAsync(load, [version])
  const { range } = useRange()
  const f = (pts: Pt[]) => pts.filter((p) => within(range, p.t))

  return (
    <section className="card">
      <header className="card-head">
        <h2>Estimated 1RM</h2>
        <div className="toggles">
          {LIFTS.map((l) => (
            <button key={l} className={`chip ${shown[l] ? 'on' : ''}`} style={{ '--c': LIFT_COLOR[l] } as React.CSSProperties}
              onClick={() => setShown((s) => ({ ...s, [l]: !s[l] }))}>
              {LIFT_LABEL[l]}
            </button>
          ))}
          <button className={`chip ${showSessions ? 'on' : ''}`} onClick={() => setShowSessions((v) => !v)}>
            Per-set
          </button>
        </div>
      </header>
      <p className="muted small">
        Line: rolling estimate (last 6 weeks, recent and low-rep sets weigh more). Faint dots: best single-set
        e1RM per session. Diamonds: actual singles.
      </p>
      {res.error && <p className="error">{res.error}</p>}
      <div className="chart">
        <ResponsiveContainer width="100%" height={320}>
          <ComposedChart margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="var(--grid)" vertical={false} />
            <XAxis dataKey="t" type="number" scale="time" domain={xDomain(range)} allowDataOverflow
              tickFormatter={shortDate} stroke="var(--muted)" fontSize={12} allowDuplicatedCategory={false} />
            <YAxis dataKey="v" unit={` ${unit()}`} domain={['auto', 'auto']} stroke="var(--muted)" fontSize={12} width={64} />
            <Tooltip contentStyle={tooltipStyle}
              labelFormatter={(t) => fmtDate(new Date(Number(t)).toISOString())}
              formatter={(v, name, item) => [`${du(Number(v))} (${(item.payload as Pt).note ?? ''})`, name]} />
            <Legend />
            {res.data &&
              LIFTS.filter((l) => shown[l]).flatMap((l) => [
                showSessions && (
                  <Scatter key={`${l}-s`} name={`${LIFT_LABEL[l]} sets`} data={f(res.data![l].sessions)} dataKey="v"
                    fill={LIFT_COLOR[l]} fillOpacity={0.3} legendType="none" isAnimationActive={false}
                    cursor="pointer" onClick={openFrom(onOpen)} />
                ),
                <Line key={`${l}-e`} name={LIFT_LABEL[l]} data={f(res.data![l].estimate)} dataKey="v"
                  stroke={LIFT_COLOR[l]} strokeWidth={2.5} dot={false} isAnimationActive={false} />,
                <Scatter key={`${l}-1`} name={`${LIFT_LABEL[l]} singles`} data={f(res.data![l].singles)} dataKey="v"
                  fill={LIFT_COLOR[l]} shape="diamond" legendType="none" isAnimationActive={false}
                  cursor="pointer" onClick={openFrom(onOpen)} />,
              ])}
            <DragZoom />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </section>
  )
}
