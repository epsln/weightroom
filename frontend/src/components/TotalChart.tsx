import { useState } from 'react'
import {
  CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { api, bigKg, fmtDate, shortDate, tooltipStyle, ts, type Sex, type TotalPoint } from '../api'
import { useAsync } from '../useAsync'
import { DragZoom, useRange } from '../range'
import { within, xDomain } from '../rangeUtils'

const SEX_KEY = 'weightroom.sex'

export function TotalChart({ version }: { version: number }) {
  const [sex, setSexState] = useState<Sex>(() => (localStorage.getItem(SEX_KEY) === 'f' ? 'f' : 'm'))
  const setSex = (s: Sex) => {
    localStorage.setItem(SEX_KEY, s)
    setSexState(s)
  }
  const res = useAsync<TotalPoint[]>(() => api.total(sex), [sex, version])
  const { range } = useRange()
  const data = (res.data ?? []).filter((p) => within(range, ts(p.date))).map((p) => ({
    t: ts(p.date),
    est: p.estimated.total != null ? Math.round(p.estimated.total) : null,
    act: p.actual.total,
    dotsEst: p.dots_estimated,
    dotsAct: p.dots_actual,
  }))
  const last = res.data?.at(-1)
  const hasDots = data.some((d) => d.dotsEst != null || d.dotsAct != null)

  return (
    <section className="card">
      <header className="card-head">
        <h2>
          SBD total
          {last?.estimated.total != null && (
            <span className="muted small">
              {' '}· est. {bigKg(last.estimated.total)}
              {last.actual.total != null && ` · actual ${bigKg(last.actual.total)}`}
              {last.dots_estimated != null && ` · ${Math.round(last.dots_estimated)} DOTS`}
            </span>
          )}
        </h2>
        <div className="toggles">
          <button className={`chip ${sex === 'm' ? 'on' : ''}`} onClick={() => setSex('m')}>M</button>
          <button className={`chip ${sex === 'f' ? 'on' : ''}`} onClick={() => setSex('f')}>F</button>
        </div>
      </header>
      {!hasDots && res.data && <p className="muted small">Add your bodyweight below to see DOTS.</p>}
      {res.error && <p className="error">{res.error}</p>}
      <div className="chart">
        <ResponsiveContainer width="100%" height={300}>
          <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="var(--grid)" vertical={false} />
            <XAxis dataKey="t" type="number" scale="time" domain={xDomain(range)} allowDataOverflow
              tickFormatter={shortDate} stroke="var(--muted)" fontSize={12} />
            <YAxis yAxisId="kg" unit=" kg" domain={['auto', 'auto']} stroke="var(--muted)" fontSize={12} width={70} />
            {hasDots && (
              <YAxis yAxisId="dots" orientation="right" domain={['auto', 'auto']} stroke="var(--muted)"
                fontSize={12} width={44} />
            )}
            <Tooltip contentStyle={tooltipStyle}
              labelFormatter={(t) => fmtDate(new Date(Number(t)).toISOString())}
              formatter={(v, name) => [String(name).includes('DOTS') ? v : bigKg(Number(v)), name]} />
            <Legend />
            <Line yAxisId="kg" dataKey="est" name="Estimated total" stroke="#22c55e" strokeWidth={2}
              dot={false} connectNulls isAnimationActive={false} />
            <Line yAxisId="kg" type="stepAfter" dataKey="act" name="Actual total (best singles)" stroke="#eab308"
              strokeDasharray="4 3" dot={false} connectNulls isAnimationActive={false} />
            {hasDots && (
              <Line yAxisId="dots" dataKey="dotsEst" name="DOTS (est.)" stroke="#94a3b8" dot={false}
                connectNulls isAnimationActive={false} />
            )}
            <DragZoom />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </section>
  )
}
