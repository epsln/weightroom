import { useState } from 'react'
import { api, fmtRelative, type SyncStatus } from '../api'
import { useAsync } from '../useAsync'

export function SyncBar({ version, onSynced }: { version: number; onSynced: () => void }) {
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
          <span className="badge warn" title="Set BOOSTCAMP_REFRESH_TOKEN and FIREBASE_API_KEY in .env">
            not configured
          </span>
        )}
      </div>
      <button className="btn" onClick={syncNow} disabled={busy}>
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
