import { createContext, useContext } from "react";
import type { MonitoringSummary } from "./api";

type MonitoringContextValue = {
  summary: MonitoringSummary | null;
  setSummary: (s: MonitoringSummary | null) => void;
};

export const MonitoringContext = createContext<MonitoringContextValue>({
  summary: null,
  setSummary: () => undefined
});

export function useMonitoringSummary() {
  return useContext(MonitoringContext).summary;
}

export function useSetMonitoringSummary() {
  return useContext(MonitoringContext).setSummary;
}
