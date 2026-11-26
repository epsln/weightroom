import { useState } from 'react'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, ts, fmtDate, LIFT_LABEL, LIFTS, tooltipStyle, ZONES, type IntensityWeek, type Lift, type Zone } from '../api'
import { LIFT_COLOR } from '../colors'
import { useAsync } from '../useAsync'
import { useRange } from '../range'
import { weeksSince, within } from '../rangeUtils'

const ZONE_COLOR: Record<Zone, string> = {
  '<70': '#334155',
  '70-80': '#0ea5e9',
  '80-90': '#f59e0b',
  '90+': '#ef4444',
}
const RANGES = [12, 26, 52] as const

export function IntensityChart({ version }: { version: number }) {
  const [weeks, setWeeks] = useState(12)
  const [lift, setLift] = useState<Lift | undefined>(undefined)
  const { range } = useRange()
  const effWeeks = range.from != null ? weeksSince(range.from) : weeks
  const res = useAsync<IntensityWeek[]>(() => api.intensity(effWeeks, lift), [effWeeks, lift, version])
  const data = res.data?.filter((w) => within({ from: range.from == null ? null : range.from - 6 * 86400000, to: range.to }, ts(w.week_start)))

  return (
    <section className="card">
      <header className="card-head">
        <h2>Intensity (sets by % of est. 1RM)</h2>
        <div className="toggles">
          <button className={`chip ${!lift ? 'on' : ''}`} onClick={() => setLift(undefined)}>All</button>
          {LIFTS.map((l) => (
            <button key={l} className={`chip ${lift === l ? 'on' : ''}`} style={{ '--c': LIFT_COLOR[l] } as React.CSSProperties}
              onClick={() => setLift(l)}>
              {LIFT_LABEL[l]}
            </button>
          ))}
          {RANGES.map((r) => (
            <button key={r} className={`chip ${weeks === r && range.from == null ? 'on' : ''}`} onClick={() => setWeeks(r)}>{r}w</button>
          ))}
        </div>
      </header>
      {res.error && <p className="error">{res.error}</p>}
      <div className="chart">
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="var(--grid)" vertical={false} />
            <XAxis dataKey="week_start" stroke="var(--muted)" fontSize={12} interval="preserveStartEnd"
              tickFormatter={(d: string) => fmtDate(d).replace(/,? \d{4}$/, '')} />
            <YAxis allowDecimals={false} stroke="var(--muted)" fontSize={12} width={40} />
            <Tooltip cursor={{ fill: 'rgba(255,255,255,0.04)' }} contentStyle={tooltipStyle}
              labelFormatter={(d) => `Week of ${fmtDate(String(d))}`}
              formatter={(v, name) => [`${v} sets`, name]} />
            <Legend />
            {ZONES.map((z) => (
              <Bar key={z} dataKey={z} name={`${z}%`} stackId="z" fill={ZONE_COLOR[z]} isAnimationActive={false} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  )
}
