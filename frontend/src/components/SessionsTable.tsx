import { useState } from 'react'
import { api, bigKg, fmtDate, type SessionPage } from '../api'
import { useAsync } from '../useAsync'

const PAGE = 20

export function SessionsTable({ version, onOpen }: { version: number; onOpen: (id: string) => void }) {
  const [offset, setOffset] = useState(0)
  const res = useAsync<SessionPage>(() => api.sessions(PAGE, offset), [offset, version])
  const page = res.data

  return (
    <section className="card">
      <header className="card-head">
        <h2>Sessions {page && <span className="muted small">· {page.total}</span>}</h2>
      </header>
      {res.error && <p className="error">{res.error}</p>}
      <div className="table-wrap">
        <table className="sessions">
          <thead>
            <tr>
              <th>Date</th>
              <th>Workout</th>
              <th className="hide-sm">Exercises</th>
              <th className="num">Sets</th>
              <th className="num hide-sm">Reps</th>
              <th className="num">Volume</th>
            </tr>
          </thead>
          <tbody>
            {page?.items.map((s) => (
              <tr key={s.id} onClick={() => onOpen(s.id)} tabIndex={0}
                onKeyDown={(e) => e.key === 'Enter' && onOpen(s.id)}>
                <td className="nowrap">{fmtDate(s.date)}</td>
                <td>
                  <div>{s.title ?? '–'}</div>
                  <div className="muted small">{s.program}</div>
                </td>
                <td className="hide-sm exercises">{s.exercises.join(' · ')}</td>
                <td className="num">{s.sets}</td>
                <td className="num hide-sm">{s.reps}</td>
                <td className="num nowrap">{bigKg(s.volume_kg)}</td>
              </tr>
            ))}
            {page && page.items.length === 0 && (
              <tr>
                <td colSpan={6} className="muted empty">No sessions yet — run a sync.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {page && page.total > PAGE && (
        <footer className="pager">
          <button className="btn ghost" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>
            ← Newer
          </button>
          <span className="muted small">
            {offset + 1}–{Math.min(offset + PAGE, page.total)} of {page.total}
          </span>
          <button className="btn ghost" disabled={offset + PAGE >= page.total} onClick={() => setOffset(offset + PAGE)}>
            Older →
          </button>
        </footer>
      )}
    </section>
  )
}
