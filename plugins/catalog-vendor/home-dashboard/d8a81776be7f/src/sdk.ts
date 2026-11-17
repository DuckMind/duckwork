// Typed access to the Duckwork dashboard plugin SDK (window.__DUCKWORK_PLUGIN_SDK__).
// The host exposes its React instance, an authenticated API client for core
// endpoints, and fetchJSON. We only declare the slice we use.
import type {
  StatusResponse, SystemStats, AnalyticsResponse,
  PaginatedSessions, LogsResponse, CronJob,
} from "./api-types";

export interface DuckworkApi {
  getStatus(): Promise<StatusResponse>;
  getSystemStats(): Promise<SystemStats>;
  getAnalytics(days: number): Promise<AnalyticsResponse>;
  getCronJobs(profile?: string): Promise<CronJob[]>;
  getSessions(limit?: number, offset?: number): Promise<PaginatedSessions>;
  getLogs(params: {
    file?: string; lines?: number; level?: string; component?: string;
  }): Promise<LogsResponse>;
}

interface DuckworkPluginSDK {
  api: DuckworkApi;
  fetchJSON: <T = unknown>(url: string, init?: RequestInit) => Promise<T>;
}

export interface DuckworkHomeHost extends DuckworkPluginSDK {
  navigateTo: (routePath: string) => void;
}

declare global {
  interface Window {
    __DUCKWORK_PLUGIN_SDK__?: Record<string, unknown>;
    __DUCKWORK_PLUGINS__?: {
      register: (name: string, component: unknown) => void;
    };
  }
}

function getDashboardHost(): DuckworkHomeHost {
  const sdk = window.__DUCKWORK_PLUGIN_SDK__;
  if (!sdk) throw new Error("Duckwork plugin SDK not available");
  const dashboard = sdk as unknown as DuckworkPluginSDK;
  return {
    ...dashboard,
    navigateTo: (routePath) => window.location.assign(routePath),
  };
}

let configuredHost: DuckworkHomeHost | null = null;

export function configureHomeHost(host: DuckworkHomeHost): void {
  configuredHost = host;
}

function getHost(): DuckworkHomeHost {
  return configuredHost ?? getDashboardHost();
}

export const api: DuckworkApi = {
  getStatus: () => getHost().api.getStatus(),
  getSystemStats: () => getHost().api.getSystemStats(),
  getAnalytics: (days) => getHost().api.getAnalytics(days),
  getCronJobs: (profile) => getHost().api.getCronJobs(profile),
  getSessions: (limit, offset) => getHost().api.getSessions(limit, offset),
  getLogs: (params) => getHost().api.getLogs(params),
};

export function fetchJSON<T = unknown>(url: string, init?: RequestInit): Promise<T> {
  return getHost().fetchJSON<T>(url, init);
}

/** Navigate to a core dashboard route. The SDK doesn't expose the host
 *  router, so this is a full-page navigation (fine for an occasional
 *  widget click-through). */
export function navigateTo(routePath: string): void {
  getHost().navigateTo(routePath);
}
