/** Global date range in ms timestamps (local midnight); null = open-ended. */
export interface DateRange {
  from: number | null
  to: number | null
}

export const ALL: DateRange = { from: null, to: null }

export const isAll = (r: DateRange) => r.from == null && r.to == null

export const within = (r: DateRange, t: number) => (r.from == null || t >= r.from) && (r.to == null || t <= r.to)

/** X-axis domain for time charts: the selected range, or fit to data. */
export const xDomain = (r: DateRange): [number | string, number | string] => [r.from ?? 'dataMin', r.to ?? 'dataMax']

export const DAY = 86400000
export const midnight = (t: number) => {
  const d = new Date(t)
  d.setHours(0, 0, 0, 0)
  return d.getTime()
}
/** Local midnight at page load. */
export const TODAY = midnight(Date.now())

/** Weeks needed to cover the range start through today (for week-bucketed endpoints). */
export const weeksSince = (from: number) => Math.min(520, Math.ceil((TODAY - from) / (7 * DAY)) + 1)
