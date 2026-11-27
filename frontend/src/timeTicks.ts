/**
 * Calendar-aligned ticks for time axes. Ticks land on local midnight / Mondays /
 * 1st of month / quarter starts / Jan 1, and labels show only the unit that
 * changes (a bigger unit is added where it rolls over). Years are never in tick
 * labels except for yearly ticks; they go in a caption under the axis instead.
 */

const DAY = 86400000
const MAX_TICKS = 8

type Step = 'day' | 'week' | 'month' | 'quarter' | 'year'

export interface TimeAxis {
  ticks: number[]
  format: (t: number) => string
  /** e.g. "2026" or "2025 – 2026"; empty when the ticks are themselves years. */
  caption: string
}

const fmt = (opts: Intl.DateTimeFormatOptions) => {
  const f = new Intl.DateTimeFormat(undefined, opts)
  return (t: number) => f.format(t)
}
const dayNum = fmt({ day: 'numeric' })
const dayMonth = fmt({ day: 'numeric', month: 'short' })
const monthName = fmt({ month: 'short' })

/** First tick boundary at or after t for the given step (local time). */
function ceil(t: number, step: Step): Date {
  const d = new Date(t)
  d.setHours(0, 0, 0, 0)
  if (d.getTime() < t) d.setDate(d.getDate() + 1)
  if (step === 'week') {
    d.setDate(d.getDate() + ((8 - d.getDay()) % 7)) // next Monday (or today)
  } else if (step !== 'day') {
    const months = step === 'month' ? 1 : step === 'quarter' ? 3 : 12
    if (d.getDate() !== 1 || d.getMonth() % months !== 0) {
      d.setDate(1)
      d.setMonth(Math.floor(d.getMonth() / months) * months + months)
    }
  }
  return d
}

function advance(d: Date, step: Step) {
  if (step === 'day') d.setDate(d.getDate() + 1)
  else if (step === 'week') d.setDate(d.getDate() + 7)
  else d.setMonth(d.getMonth() + (step === 'month' ? 1 : step === 'quarter' ? 3 : 12))
}

function ticksFor(lo: number, hi: number, step: Step): number[] {
  const out: number[] = []
  for (const d = ceil(lo, step); d.getTime() <= hi && out.length <= MAX_TICKS * 2; advance(d, step)) out.push(d.getTime())
  return out
}

const STEPS: Step[] = ['day', 'week', 'month', 'quarter', 'year']

export function timeAxis(lo: number, hi: number): TimeAxis {
  if (!(hi > lo)) hi = lo + DAY
  let step: Step = 'year'
  let ticks: number[] = []
  for (const s of STEPS) {
    ticks = ticksFor(lo, hi, s)
    step = s
    if (ticks.length <= MAX_TICKS) break
  }
  // Yearly ticks may still be too dense over very long spans: thin them out.
  if (ticks.length > MAX_TICKS) {
    const k = Math.ceil(ticks.length / MAX_TICKS)
    ticks = ticks.filter((t) => new Date(t).getFullYear() % k === 0)
  }

  const first = ticks[0]
  const isDayStep = step === 'day' || step === 'week'
  const format = (t: number) => {
    const d = new Date(t)
    if (step === 'year') return String(d.getFullYear())
    if (isDayStep) {
      // Month shown on the first tick and wherever the month changes.
      const prev = ticks[ticks.indexOf(t) - 1]
      const newMonth = t === first || prev == null || new Date(prev).getMonth() !== d.getMonth()
      return newMonth ? dayMonth(t) : dayNum(t)
    }
    return monthName(t)
  }

  const y0 = new Date(lo).getFullYear()
  const y1 = new Date(hi).getFullYear()
  const caption = step === 'year' ? '' : y0 === y1 ? String(y0) : `${y0} – ${y1}`
  return { ticks, format, caption }
}
