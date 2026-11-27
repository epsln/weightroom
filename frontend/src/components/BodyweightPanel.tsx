import { useState } from 'react'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, du, fmtDate, kg, toKg, unit, wr, tooltipStyle, ts, type BodyweightEntry } from '../api'
import { useAsync } from '../useAsync'
import { AxisCaption, DragZoom, useRange, useTimeAxis } from '../range'
import { within, xDomain } from '../rangeUtils'

const today = () => {
  const d = new Date()
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10)
}

export function BodyweightPanel({ version, onChanged }: { version: number; onChanged: () => void }) {
  const [local, setLocal] = useState(0)
  const res = useAsync<BodyweightEntry[]>(() => api.bodyweight(), [version, local])
  const [date, setDate] = useState(today)
  const [value, setValue] = useState('')
  const [err, setErr] = useState<string>()

  const run = async (p: Promise<unknown>) => {
    setErr(undefined)
    try {
      await p
      setLocal((v) => v + 1)
      onChanged()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }
  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    const n = Number(value.replace(',', '.'))
    if (!n) return
    void run(api.addBodyweight(date, Math.round(toKg(n) * 100) / 100)).then(() => setValue(''))
  }
  const entries = res.data ?? []
  const { range } = useRange()
  const data = entries.map((b) => ({ t: ts(b.date), kg: wr(b.kg) })).filter((p) => within(range, p.t))
  const axis = useTimeAxis(data.map((p) => p.t))

  return (
    <section className="card">
      <header className="card-head">
        <h2>
          Bodyweight
          {entries.length > 0 && <span className="muted small"> · {kg(entries.at(-1)!.kg)}</span>}
        </h2>
        <form className="toggles" onSubmit={submit}>
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
          <input type="number" step="0.1" min={Math.ceil(wr(20.1))} max={Math.floor(wr(399))} placeholder={unit()} value={value}
            onChange={(e) => setValue(e.target.value)} required style={{ width: 80 }} />
          <button className="chip on" type="submit">Save</button>
        </form>
      </header>
      {(err || res.error) && <p className="error">{err || res.error}</p>}
      {data.length > 1 && (
        <div className="chart">
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
              <CartesianGrid stroke="var(--grid)" vertical={false} />
              <XAxis dataKey="t" type="number" scale="time" domain={xDomain(range)} allowDataOverflow
                ticks={axis.ticks} tickFormatter={axis.format} stroke="var(--muted)" fontSize={12} />
              <YAxis unit={` ${unit()}`} domain={['auto', 'auto']} stroke="var(--muted)" fontSize={12} width={64} />
              <Tooltip contentStyle={tooltipStyle} labelFormatter={(t) => fmtDate(new Date(Number(t)).toISOString())}
                formatter={(v) => [du(Number(v)), 'Bodyweight']} />
              <Line dataKey="kg" stroke="#e2e8f0" dot={{ r: 2 }} isAnimationActive={false} />
              <DragZoom />
            </LineChart>
          </ResponsiveContainer>
          <AxisCaption axis={axis} />
        </div>
      )}
      {entries.length > 0 && (
        <div className="table-wrap">
          <table className="sessions">
            <tbody>
              {entries.slice(-5).reverse().map((b) => (
                <tr key={b.date}>
                  <td>{fmtDate(b.date)}</td>
                  <td>{kg(b.kg)}</td>
                  <td><button className="link" onClick={() => void run(api.deleteBodyweight(b.date))}>delete</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {entries.length === 0 && res.data && <p className="muted">No entries yet. Used for DOTS on the total chart.</p>}
    </section>
  )
}
