// Perf instrumentation for the full render pipeline.
//
//   PerfPane (React.Profiler)  -> per-pane commit times
//   logFrameEvent (ink.onFrame) -> yoga / renderer / diff / optimize / write
//                                 phases + yoga counters + scroll fast-path
//
// Both gate on HERMES_DEV_PERF=1 and dump JSON-lines through perfLog.ts
// (default ~/.hermes/perf.log, override HERMES_DEV_PERF_LOG). Tagged
// { src: 'react' | 'frame' | 'startup' } for jq. HERMES_DEV_PERF_MS
// (default 2) skips sub-ms idle frames; set 0 to capture all.
//
// Zero cost when unset: PerfPane returns children directly, logFrameEvent is
// undefined so ink doesn't pay the timing cost.

import type { FrameEvent } from '@hermes/ink'
import { scrollFastPathStats } from '@hermes/ink'
import { Profiler, type ProfilerOnRenderCallback, type ReactNode } from 'react'

import { PERF_ENABLED, PERF_THRESHOLD_MS, writePerfRow } from './perfLog.js'

const round2 = (n: number) => Math.round(n * 100) / 100

const onRender: ProfilerOnRenderCallback = (id, phase, actualMs, baseMs, startTime, commitTime) => {
  if (actualMs < PERF_THRESHOLD_MS) {
    return
  }

  writePerfRow({
    actualMs: round2(actualMs),
    baseMs: round2(baseMs),
    commitTimeMs: round2(commitTime),
    id,
    phase,
    src: 'react',
    startTimeMs: round2(startTime),
    ts: Date.now()
  })
}

export function PerfPane({ children, id }: { children: ReactNode; id: string }) {
  if (!PERF_ENABLED) {
    return children
  }

  return (
    <Profiler id={id} onRender={onRender}>
      {children}
    </Profiler>
  )
}

export const logFrameEvent = PERF_ENABLED
  ? (event: FrameEvent) => {
      if (event.durationMs < PERF_THRESHOLD_MS) {
        return
      }

      writePerfRow({
        durationMs: round2(event.durationMs),
        // Cumulative counters: consumers diff pairs to get per-frame deltas.
        fastPath: { ...scrollFastPathStats, declined: { ...scrollFastPathStats.declined } },
        flickers: event.flickers.length ? event.flickers : undefined,
        phases: event.phases
          ? {
              ...event.phases,
              commit: round2(event.phases.commit),
              diff: round2(event.phases.diff),
              optimize: round2(event.phases.optimize),
              prevFrameDrainMs: round2(event.phases.prevFrameDrainMs),
              renderer: round2(event.phases.renderer),
              write: round2(event.phases.write),
              yoga: round2(event.phases.yoga)
            }
          : undefined,
        src: 'frame',
        ts: Date.now(),
        uptimeMs: Math.round(process.uptime() * 1000)
      })
    }
  : undefined
