import { useState } from 'react'
import { api, fmtRelative, type SyncStatus } from '../api'
import { useAsync } from '../useAsync'

export function SyncBar({ version, onSynced, onSettings }: { version: number; onSynced: () => void; onSettings: () => void }) {
  const [busy, setBusy] = useState(false)
  const [syncError, setSyncError] = useState<string>()
  const status = useAsync<SyncStatus>(() => api.syncStatus(), [version])

  async function syncNow() {
    setBusy(true)
    setSyncError(undefined)
    try {
      const row = await api.sync()
      if (!row.ok) setSyncError(row.error ?? 'Sync failed')
      onSynced()
    } catch (e) {
      setSyncError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  const last = status.data?.last
  const lastError = syncError ?? (last && !last.ok ? last.error : undefined)

  return (
    <div className="syncbar">
      <div className="syncbar-text">
        <span className="muted">Last sync</span>{' '}
        <span title={last?.last_success_at ?? undefined}>{fmtRelative(last?.last_success_at)}</span>
        {status.data && !status.data.configured && (
          <button className="badge warn link" onClick={onSettings} title="Connect Boostcamp in Settings">
            not connected
          </button>
        )}
      </div>
      <button className="btn" onClick={syncNow} disabled={busy || status.data?.configured === false}>
        {busy ? 'Syncing…' : 'Sync now'}
      </button>
      {lastError && (
        <div className="syncbar-error" title={lastError}>
          {lastError}
        </div>
      )}
    </div>
  )
}
