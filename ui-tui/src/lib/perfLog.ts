// JSON-lines sink for HERMES_DEV_PERF. One writer keeps frame, React, and
// startup rows on the same flag, path, and best-effort semantics.

import { appendFileSync, mkdirSync } from 'node:fs'
import { homedir } from 'node:os'
import { dirname, join } from 'node:path'

export const PERF_ENABLED = /^(?:1|true|yes|on)$/i.test((process.env.HERMES_DEV_PERF ?? '').trim())
export const PERF_THRESHOLD_MS = Number(process.env.HERMES_DEV_PERF_MS ?? '2') || 0
export const PERF_LOG_PATH =
  process.env.HERMES_DEV_PERF_LOG?.trim() || join(homedir(), '.hermes', 'perf.log')

let logReady = false

export const writePerfRow = (row: Record<string, unknown>) => {
  if (!logReady) {
    logReady = true

    try {
      mkdirSync(dirname(PERF_LOG_PATH), { recursive: true })
    } catch {
      // Best-effort: never crash the TUI to log a sample.
    }
  }

  try {
    appendFileSync(PERF_LOG_PATH, `${JSON.stringify(row)}\n`)
  } catch {
    // Best-effort.
  }
}
