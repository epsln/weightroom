import { bigKg, fmtDate, kg, unit, wr, LIFT_LABEL, LIFTS, type Lift, type LiftPrs, type Prs, type SetRef } from '../api'

function PrRow({ label, value, sub, onOpen, sessionId }: {
  label: string
  value: string
  sub?: string
  sessionId?: string
  onOpen: (id: string) => void
}) {
  return (
    <div className="pr-row">
      <span className="muted">{label}</span>
      <span className="pr-value">{value}</span>
      {sub && sessionId ? (
        <button className="link pr-sub" onClick={() => onOpen(sessionId)}>
          {sub}
        </button>
      ) : (
        <span className="pr-sub muted">{sub}</span>
      )}
    </div>
  )
}

const setStr = (s: SetRef | null) => (s ? `${kg(s.weight_kg)} × ${s.reps}` : '–')

function PrCard({ lift, prs, onOpen }: { lift: Lift; prs: LiftPrs; onOpen: (id: string) => void }) {
  const e1rm = prs.best_e1rm
  const est = prs.estimated_1rm
  return (
    <section className={`card pr-card lift-${lift}`}>
      <header className="pr-head">
        <h3>{LIFT_LABEL[lift]}</h3>
        <div className="pr-hero" title="Rolling estimate from the last 6 weeks of training">
          <span className="pr-hero-value">{est ? wr(est.e1rm_kg) : '–'}</span>
          <span className="muted"> {unit()} est. 1RM</span>
        </div>
      </header>
      <PrRow label="Best single" value={setStr(prs.best_single)}
        sub={prs.best_single ? fmtDate(prs.best_single.date) : undefined}
        sessionId={prs.best_single?.session_id} onOpen={onOpen} />
      <PrRow label="Best e1RM" value={e1rm?.e1rm_kg != null ? kg(e1rm.e1rm_kg) : '–'}
        sub={e1rm ? `${setStr(e1rm)}, ${fmtDate(e1rm.date)}` : undefined}
        sessionId={e1rm?.session_id} onOpen={onOpen} />
      <PrRow label="Heaviest" value={setStr(prs.heaviest)} sub={prs.heaviest ? fmtDate(prs.heaviest.date) : undefined}
        sessionId={prs.heaviest?.session_id} onOpen={onOpen} />
      <PrRow label="Set volume" value={prs.best_set_volume ? bigKg(prs.best_set_volume.volume_kg) : '–'}
        sub={prs.best_set_volume ? fmtDate(prs.best_set_volume.date) : undefined}
        sessionId={prs.best_set_volume?.session_id} onOpen={onOpen} />
      <PrRow label="Session volume" value={prs.best_session_volume ? bigKg(prs.best_session_volume.volume_kg) : '–'}
        sub={prs.best_session_volume ? fmtDate(prs.best_session_volume.date) : undefined}
        sessionId={prs.best_session_volume?.session_id} onOpen={onOpen} />
      <PrRow label="Last PR" value={prs.days_since_pr != null ? `${prs.days_since_pr} days ago` : '–'} onOpen={onOpen} />

      <table className="rm-table">
        <thead>
          <tr>
            {Object.keys(prs.rep_maxes).map((n) => (
              <th key={n}>{n}RM</th>
            ))}
          </tr>
        </thead>
        <tbody>
          <tr>
            {Object.entries(prs.rep_maxes).map(([n, s]) => (
              <td key={n}>
                {s ? (
                  <button className="link" onClick={() => onOpen(s.session_id)}
                    title={`${setStr(s)} on ${fmtDate(s.date)}`}>
                    {wr(s.weight_kg)}
                  </button>
                ) : (
                  '–'
                )}
              </td>
            ))}
          </tr>
        </tbody>
      </table>
    </section>
  )
}

export function PrCards({ prs, onOpen }: { prs: Prs; onOpen: (id: string) => void }) {
  return (
    <div className="pr-grid">
      {LIFTS.map((lift) => (
        <PrCard key={lift} lift={lift} prs={prs[lift]} onOpen={onOpen} />
      ))}
    </div>
  )
}
