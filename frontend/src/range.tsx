import { createContext, useContext, useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import { usePlotArea, useXAxisInverseScale } from 'recharts'
import { ALL, DAY, isAll, midnight, TODAY, type DateRange } from './rangeUtils'

interface Ctx {
  range: DateRange
  setRange: (r: DateRange) => void
}

const RangeContext = createContext<Ctx>({ range: ALL, setRange: () => {} })

export function RangeProvider({ children }: { children: ReactNode }) {
  const [range, setRange] = useState<DateRange>(ALL)
  return <RangeContext.Provider value={{ range, setRange }}>{children}</RangeContext.Provider>
}

export const useRange = () => useContext(RangeContext)

const toInput = (t: number | null) => {
  if (t == null) return ''
  const d = new Date(t)
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10)
}
const fromInput = (s: string) => (s ? new Date(`${s}T00:00:00`).getTime() : null)

const PRESETS: { label: string; days: number | null }[] = [
  { label: '1m', days: 30 },
  { label: '3m', days: 91 },
  { label: '6m', days: 182 },
  { label: '1y', days: 365 },
  { label: '2y', days: 730 },
  { label: 'All', days: null },
]

export function RangeBar() {
  const { range, setRange } = useRange()
  const today = TODAY
  const activePreset = PRESETS.find((p) =>
    p.days == null ? isAll(range) : range.to == null && range.from === today - p.days * DAY,
  )

  return (
    <div className="range-bar">
      <span className="muted small">Date range</span>
      <div className="toggles">
        {PRESETS.map((p) => (
          <button key={p.label} className={`chip ${activePreset === p ? 'on' : ''}`}
            onClick={() => setRange(p.days == null ? ALL : { from: today - p.days * DAY, to: null })}>
            {p.label}
          </button>
        ))}
      </div>
      <input type="date" value={toInput(range.from)} max={toInput(range.to)}
        onChange={(e) => setRange({ ...range, from: fromInput(e.target.value) })} />
      <span className="muted">→</span>
      <input type="date" value={toInput(range.to)} min={toInput(range.from)}
        onChange={(e) => setRange({ ...range, to: fromInput(e.target.value) })} />
      {!isAll(range) && (
        <button className="link small" onClick={() => setRange(ALL)}>Reset</button>
      )}
      <span className="muted small hint">Tip: drag on a time chart to zoom</span>
    </div>
  )
}

/**
 * Drop inside a time-axis Recharts chart. Click-and-drag across the plot draws a
 * rectangle; on release the global date range is set to the selected span.
 * Uses native listeners so tooltips and point clicks keep working.
 */
export function DragZoom({ xAxisId }: { xAxisId?: string | number }) {
  const { setRange } = useRange()
  const plot = usePlotArea()
  const invert = useXAxisInverseScale(xAxisId)
  const ref = useRef<SVGGElement>(null)
  const [drag, setDrag] = useState<{ a: number; b: number } | null>(null)
  const ready = plot != null
  const latest = useRef({ plot, invert, setRange })
  useLayoutEffect(() => {
    latest.current = { plot, invert, setRange }
  })

  useEffect(() => {
    const svg = ref.current?.ownerSVGElement
    if (!svg) return
    let start: number | null = null
    const px = (e: MouseEvent) => {
      const p = latest.current.plot!
      const x = e.clientX - svg.getBoundingClientRect().left
      return Math.min(Math.max(x, p.x), p.x + p.width)
    }
    const move = (e: MouseEvent) => {
      if (start != null) setDrag({ a: start, b: px(e) })
    }
    const up = (e: MouseEvent) => {
      window.removeEventListener('mousemove', move)
      window.removeEventListener('mouseup', up)
      if (start == null) return
      const end = px(e)
      const [a, b] = [Math.min(start, end), Math.max(start, end)]
      start = null
      setDrag(null)
      const inv = latest.current.invert
      if (b - a < 8 || !inv) return
      const from = Number(inv(a))
      const to = Number(inv(b))
      if (Number.isFinite(from) && Number.isFinite(to) && to > from) {
        latest.current.setRange({ from: midnight(from), to: midnight(to) + DAY - 1 })
      }
    }
    const down = (e: MouseEvent) => {
      const p = latest.current.plot
      if (e.button !== 0 || !p) return
      const r = svg.getBoundingClientRect()
      const x = e.clientX - r.left
      const y = e.clientY - r.top
      if (x < p.x || x > p.x + p.width || y < p.y || y > p.y + p.height) return
      e.preventDefault() // no text selection while dragging
      start = x
      window.addEventListener('mousemove', move)
      window.addEventListener('mouseup', up)
    }
    svg.addEventListener('mousedown', down)
    svg.style.cursor = 'crosshair'
    return () => {
      svg.removeEventListener('mousedown', down)
      window.removeEventListener('mousemove', move)
      window.removeEventListener('mouseup', up)
    }
  }, [ready])

  return (
    <g ref={ref}>
      {drag && plot && (
        <rect x={Math.min(drag.a, drag.b)} y={plot.y} width={Math.abs(drag.b - drag.a)} height={plot.height}
          fill="#38bdf8" fillOpacity={0.15} stroke="#38bdf8" strokeOpacity={0.6} pointerEvents="none" />
      )}
    </g>
  )
}
