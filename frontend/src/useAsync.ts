import { useEffect, useState } from 'react'

export interface AsyncState<T> {
  data: T | undefined
  error: string | undefined
  loading: boolean
}

/** Runs `fn` whenever `deps` change; ignores results from stale calls. */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [state, setState] = useState<AsyncState<T>>({ data: undefined, error: undefined, loading: true })

  useEffect(() => {
    let alive = true
    setState((s) => ({ ...s, loading: true, error: undefined }))
    fn().then(
      (data) => alive && setState({ data, error: undefined, loading: false }),
      (err: unknown) =>
        alive && setState((s) => ({ ...s, error: err instanceof Error ? err.message : String(err), loading: false })),
    )
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  return state
}
