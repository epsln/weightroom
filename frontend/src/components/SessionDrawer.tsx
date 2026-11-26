import { useEffect } from 'react'
import { api, bigKg, fmtDate, kg, type SessionDetail } from '../api'
import { LIFT_COLOR } from '../colors'
import { useAsync } from '../useAsync'

export function SessionDrawer({ id, onClose }: { id: string; onClose: () => void }) {
  const res = useAsync<SessionDetail>(() => api.session(id), [id])
  const s = res.data

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside className="drawer" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <header className="drawer-head">
          <div>
            <h2>{s?.title ?? 'Session'}</h2>
            {s && (
              <div className="muted small">
                {fmtDate(s.date)} · {s.finished_at.slice(11, 16)} · {s.program}
              </div>
            )}
          </div>
          <button className="btn ghost" onClick={onClose} aria-label="Close">✕</button>
        </header>

        {res.error && <p className="error">{res.error}</p>}
        {res.loading && !s && <p className="muted">Loading…</p>}

        {s && (
          <>
            <div className="stat-row">
              <div><span className="muted small">Volume</span><strong>{bigKg(s.volume_kg)}</strong></div>
              <div><span className="muted small">Sets</span><strong>{s.sets}</strong></div>
              <div><span className="muted small">Reps</span><strong>{s.reps}</strong></div>
            </div>

            {s.exercises.length === 0 && <p className="muted">No completed sets recorded.</p>}

            {s.exercises.map((ex, i) => (
              <section key={i} className="exercise">
                <header>
                  <h3>
                    {ex.lift && <span className="dot" style={{ background: LIFT_COLOR[ex.lift] }} />}
                    {ex.exercise}
                  </h3>
                  <span className="muted small">
                    {bigKg(ex.volume_kg)}
                    {ex.best_e1rm_kg != null && ` · e1RM ${kg(Math.round(ex.best_e1rm_kg * 10) / 10)}`}
                  </span>
                </header>
                <table className="sets">
                  <thead>
                    <tr><th>Set</th><th className="num">Weight</th><th className="num">Reps</th><th className="num">Volume</th><th className="num">e1RM</th></tr>
                  </thead>
                  <tbody>
                    {ex.sets.map((st) => (
                      <tr key={st.set_idx}>
                        <td className="muted">{st.set_idx + 1}</td>
                        <td className="num">{kg(st.weight_kg)}</td>
                        <td className="num">{st.reps}</td>
                        <td className="num">{bigKg(st.volume_kg)}</td>
                        <td className="num muted">{st.e1rm_kg != null ? Math.round(st.e1rm_kg * 10) / 10 : '–'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </section>
            ))}
          </>
        )}
      </aside>
    </div>
  )
}
