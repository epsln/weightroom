import { useState } from 'react'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, ts, bigKg, fmtDate, LIFT_LABEL, type WeekVolume } from '../api'
import { LIFT_COLOR } from '../colors'
import { useAsync } from '../useAsync'
import { useRange } from '../range'
import { weeksSince, within } from '../rangeUtils'

const RANGES = [12, 26, 52] as const
const STACKS = ['squat', 'bench', 'deadlift', 'other'] as const

const tonnes = (v: number) => (v >= 1000 ? `${Math.round(v / 100) / 10}t` : `${v}`)

export function WeeklyVolumeChart({ version }: { version: number }) {
  const [weeks, setWeeks] = useState<number>(12)
  const { range } = useRange()
  const effWeeks = range.from != null ? weeksSince(range.from) : weeks
  const res = useAsync<WeekVolume[]>(() => api.weekly(effWeeks), [effWeeks, version])
  const data = res.data?.filter((w) => within({ from: range.from == null ? null : range.from - 6 * 86400000, to: range.to }, ts(w.week_start))).map((w) => ({ ...w, label: `W${w.iso_week}` }))
  const current = res.data?.at(-1)

  return (
    <section className="card">
      <header className="card-head">
        <h2>
          Weekly volume
          {current && <span className="muted small"> · this week {bigKg(current.total)}</span>}
        </h2>
        <div className="toggles">
          {RANGES.map((r) => (
            <button key={r} className={`chip ${weeks === r && range.from == null ? 'on' : ''}`} onClick={() => setWeeks(r)}>
              {r}w
            </button>
          ))}
        </div>
      </header>
      {res.error && <p className="error">{res.error}</p>}
      <div className="chart">
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="var(--grid)" vertical={false} />
            <XAxis dataKey="label" stroke="var(--muted)" fontSize={12} interval="preserveStartEnd" />
            <YAxis tickFormatter={tonnes} stroke="var(--muted)" fontSize={12} width={48} />
            <Tooltip
              cursor={{ fill: 'rgba(255,255,255,0.04)' }}
              contentStyle={{ background: 'var(--panel-2)', border: '1px solid var(--border)', borderRadius: 8 }}
              labelFormatter={(_l, p) => {
                const w = p?.[0]?.payload as WeekVolume | undefined
                return w ? `Week of ${fmtDate(w.week_start)} · ${w.sessions} sessions · ${bigKg(w.total)}` : ''
              }}
              formatter={(v, name) => [bigKg(Number(v)), name]}
            />
            <Legend />
            {STACKS.map((k) => (
              <Bar key={k} dataKey={k} stackId="v" fill={LIFT_COLOR[k]} isAnimationActive={false}
                name={k === 'other' ? 'Other' : LIFT_LABEL[k]} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  )
}
