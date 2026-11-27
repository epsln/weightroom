import { useState } from 'react'
import {
  CartesianGrid, ComposedChart, Line, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis,
} from 'recharts'
import { api, du, fmtDate, unit, wr, LIFT_LABEL, LIFTS, tooltipStyle, ts, type ActualMax, type Lift } from '../api'
import { LIFT_COLOR } from '../colors'
import { useAsync } from '../useAsync'
import { AxisCaption, DragZoom, useRange, useTimeAxis } from '../range'
import { within, xDomain } from '../rangeUtils'

interface Pt {
  t: number
  w: number
  best: number
  reps: number
  is_pr: boolean
  session_id: string
}

// Custom tooltip: Scatter would otherwise list the raw x value (t, a timestamp) as a row.
function HeaviestTooltip({ active, payload }: { active?: boolean; payload?: readonly { payload?: Pt }[] }) {
  const p = active ? payload?.[0]?.payload : undefined
  if (!p) return null
  return (
    <div style={{ ...tooltipStyle, padding: '8px 10px' }}>
      <div style={{ marginBottom: 4 }}>{fmtDate(new Date(p.t).toISOString())}</div>
      <div>{du(p.w)} × {p.reps}{p.is_pr ? ' · new best' : ''}</div>
      <div className="muted">Running best: {du(p.best)}</div>
    </div>
  )
}

export function ActualMaxChart({ version, onOpen }: { version: number; onOpen: (id: string) => void }) {
  const [lift, setLift] = useState<Lift>('squat')
  const res = useAsync<ActualMax[]>(() => api.actualMaxes(lift), [lift, version])
  const { range } = useRange()
  const all: Pt[] = (res.data ?? []).map((m) => ({
    t: ts(m.date), w: wr(m.weight_kg), reps: m.reps, best: wr(m.running_best_kg), is_pr: m.is_pr, session_id: m.session_id,
  }))
  const pts = all.filter((p) => within(range, p.t))
  const axis = useTimeAxis(pts.map((p) => p.t))
  const prs = pts.filter((p) => p.is_pr)
  const other = pts.filter((p) => !p.is_pr)
  const color = LIFT_COLOR[lift]
  const open = (p: unknown) => {
    const id = (p as { payload?: Pt }).payload?.session_id
    if (id) onOpen(id)
  }

  return (
    <section className="card">
      <header className="card-head">
        <h2>
          Heaviest sets
          {all.length > 0 && <span className="muted small"> · best {du(all.at(-1)!.best)}</span>}
        </h2>
        <div className="toggles">
          {LIFTS.map((l) => (
            <button key={l} className={`chip ${lift === l ? 'on' : ''}`} style={{ '--c': LIFT_COLOR[l] } as React.CSSProperties}
              onClick={() => setLift(l)}>
              {LIFT_LABEL[l]}
            </button>
          ))}
        </div>
      </header>
      {res.error && <p className="error">{res.error}</p>}
      {res.data && pts.length === 0 && <p className="muted">No sets for {LIFT_LABEL[lift]} in this range.</p>}
      {pts.length > 0 && (
        <div className="chart">
          <ResponsiveContainer width="100%" height={300}>
            <ComposedChart data={pts} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
              <CartesianGrid stroke="var(--grid)" vertical={false} />
              <XAxis dataKey="t" type="number" scale="time" domain={xDomain(range)} allowDataOverflow
                ticks={axis.ticks} tickFormatter={axis.format} stroke="var(--muted)" fontSize={12} />
              <YAxis unit={` ${unit()}`} domain={['auto', 'auto']} stroke="var(--muted)" fontSize={12} width={64} />
              <Tooltip content={HeaviestTooltip} />
              <Line type="stepAfter" dataKey="best" name="Running best" stroke={color} strokeDasharray="4 3"
                dot={false} isAnimationActive={false} />
              <Scatter data={other} dataKey="w" name="Heaviest set" fill={color} fillOpacity={0.45}
                isAnimationActive={false} cursor="pointer" onClick={open} />
              <Scatter data={prs} dataKey="w" name="New best" fill={color} shape="star"
                isAnimationActive={false} cursor="pointer" onClick={open} />
              <DragZoom />
            </ComposedChart>
          </ResponsiveContainer>
          <AxisCaption axis={axis} />
        </div>
      )}
    </section>
  )
}
