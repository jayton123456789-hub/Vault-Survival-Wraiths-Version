import type { RunnerState } from "./state";

export type LogType = "travel" | "event" | "choice" | "outcome" | "death" | "system";

export interface LogEntry {
  readonly step: number;
  readonly time: number;
  readonly distance: number;
  readonly type: LogType;
  readonly line: string;
  readonly data?: Record<string, unknown>;
}

export function createLogEntry(
  state: RunnerState,
  type: LogType,
  line: string,
  data?: Record<string, unknown>
): LogEntry {
  return {
    step: state.step,
    time: state.time,
    distance: state.distance,
    type,
    line,
    data
  };
}

export function formatLogEntry(entry: LogEntry): string {
  const step = String(entry.step).padStart(3, "0");
  const time = String(entry.time).padStart(3, "0");
  const distance = entry.distance.toFixed(2).padStart(8, " ");
  return `[s=${step} t=${time} d=${distance}] [${entry.type.toUpperCase()}] ${entry.line}`;
}
