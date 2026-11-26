import { LB_PER_KG, type Units } from './api'

export const errMsg = (e: unknown) => (e instanceof Error ? e.message : String(e))

export const todayIso = () => {
  const d = new Date()
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10)
}

/** Shown when the page is served over plain HTTP from a non-local host. */
export const insecureOrigin = () =>
  location.protocol !== 'https:' && !['localhost', '127.0.0.1', '[::1]'].includes(location.hostname)

export const CURRENT_YEAR = new Date().getFullYear()

/** Converts a typed value in `units` to kg; returns null if empty/invalid/out of range. */
export function parseWeight(value: string, units: Units): number | null {
  const n = Number(value.replace(',', '.'))
  if (!value.trim() || !Number.isFinite(n) || n <= 0) return null
  const kg = units === 'lb' ? n / LB_PER_KG : n
  return kg > 20 && kg < 400 ? Math.round(kg * 100) / 100 : null
}

