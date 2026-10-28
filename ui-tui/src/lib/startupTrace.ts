// Local startup timeline for scripts/perf/startup.py.
//
// Gated on HERMES_DEV_PERF=1 and written to the shared perf log. The first
// occurrence of each phase wins, so reconnects and repeated session.info
// events never skew a cold-start measurement. Zero cost when unset:
// traceStartup is undefined and every call site short-circuits.

import { PERF_ENABLED, writePerfRow } from './perfLog.js'

const seen = new Set<string>()

export const traceStartup = PERF_ENABLED
  ? (phase: string) => {
      if (seen.has(phase)) {
        return
      }

      seen.add(phase)
      writePerfRow({
        phase,
        pid: process.pid,
        src: 'startup',
        ts: Date.now(),
        uptimeMs: Math.round(process.uptime() * 1000)
      })
    }
  : undefined

if (traceStartup) {
  traceStartup('module_eval')
}
