import { useState } from 'react'
import { api, fmtDate, ts, kg, wr, LIFT_LABEL, LIFTS, type Lift, type PrTimeline as Timeline } from '../api'
import { LIFT_COLOR } from '../colors'
import { useAsync } from '../useAsync'
import { useRange } from '../range'
import { within } from '../rangeUtils'

const PAGE = 25

export function PrTimeline({ version, onOpen }: { version: number; onOpen: (id: string) => void }) {
  const res = useAsync<Timeline>(() => api.prTimeline(), [version])
  const [lift, setLift] = useState<Lift | undefined>(undefined)
  const [limit, setLimit] = useState(PAGE)
  const { range } = useRange()
  const events = (res.data?.events ?? []).filter((e) => (!lift || e.lift === lift) && within(range, ts(e.date)))

  return (
    <section className="card">
      <header className="card-head">
        <h2>PR timeline</h2>
        <div className="toggles">
          <button className={`chip ${!lift ? 'on' : ''}`} onClick={() => setLift(undefined)}>All</button>
          {LIFTS.map((l) => (
            <button key={l} className={`chip ${lift === l ? 'on' : ''}`} style={{ '--c': LIFT_COLOR[l] } as React.CSSProperties}
              onClick={() => setLift(l)}>
              {LIFT_LABEL[l]}
              {res.data?.days_since[l] != null && <span className="muted"> · {res.data.days_since[l]}d</span>}
            </button>
          ))}
        </div>
      </header>
      {res.error && <p className="error">{res.error}</p>}
      <div className="table-wrap">
        <table className="sessions">
          <thead>
            <tr><th>Date</th><th>Lift</th><th>PR</th><th>Value</th><th>Set</th><th>Previous</th></tr>
          </thead>
          <tbody>
            {events.slice(0, limit).map((e, i) => (
              <tr key={`${e.session_id}-${e.kind}-${i}`} className="clickable" onClick={() => onOpen(e.session_id)}>
                <td>{fmtDate(e.date)}</td>
                <td style={{ color: LIFT_COLOR[e.lift] }}>{LIFT_LABEL[e.lift]}</td>
                <td>{e.kind}</td>
                <td>{kg(e.value)}</td>
                <td className="muted">{kg(e.weight_kg)} × {e.reps}</td>
                <td className="muted">
                  {e.previous != null ? `${kg(e.previous)} (+${wr(e.value - e.previous)})` : 'first'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {events.length > limit && (
        <button className="link" onClick={() => setLimit((l) => l + PAGE)}>Show more ({events.length - limit} left)</button>
      )}
    </section>
  )
}
