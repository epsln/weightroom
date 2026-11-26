import { useState } from 'react'
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, LIFT_LABEL, LIFTS, tooltipStyle, type Lift, type RepCurvePoint } from '../api'
import { LIFT_COLOR } from '../colors'
import { useAsync } from '../useAsync'

export function RepCurveChart({ version }: { version: number }) {
  const [lift, setLift] = useState<Lift>('squat')
  const res = useAsync<RepCurvePoint[]>(() => api.repCurve(lift), [lift, version])
  const color = LIFT_COLOR[lift]

  return (
    <section className="card">
      <header className="card-head">
        <h2>Rep-max curve</h2>
        <div className="toggles">
          {LIFTS.map((l) => (
            <button key={l} className={`chip ${lift === l ? 'on' : ''}`} style={{ '--c': LIFT_COLOR[l] } as React.CSSProperties}
              onClick={() => setLift(l)}>
              {LIFT_LABEL[l]}
            </button>
          ))}
        </div>
      </header>
      <p className="muted small">Heaviest weight lifted for at least N reps.</p>
      {res.error && <p className="error">{res.error}</p>}
      <div className="chart">
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={res.data} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="var(--grid)" vertical={false} />
            <XAxis dataKey="reps" stroke="var(--muted)" fontSize={12} tickFormatter={(r) => `${r}RM`} />
            <YAxis unit=" kg" domain={['auto', 'auto']} stroke="var(--muted)" fontSize={12} width={64} />
            <Tooltip contentStyle={tooltipStyle} labelFormatter={(r) => `${r} reps`}
              formatter={(v, name) => [v == null ? '–' : `${v} kg`, name]} />
            <Legend />
            <Line dataKey="all" name="All time" stroke={color} strokeWidth={2} isAnimationActive={false} connectNulls />
            <Line dataKey="d90" name="Last 90 days" stroke={color} strokeOpacity={0.7} strokeDasharray="6 3"
              isAnimationActive={false} connectNulls />
            <Line dataKey="d30" name="Last 30 days" stroke="var(--muted)" strokeDasharray="2 3"
              isAnimationActive={false} connectNulls />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  )
}
