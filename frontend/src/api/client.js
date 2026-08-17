import { getAccessToken, getRefreshToken, setAccessToken, clearTokens } from "./tokenStorage";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:5000";

export class ApiError extends Error {
  constructor(status, code, message, details) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

let refreshInFlight = null;

async function doRefresh() {
  const refreshToken = getRefreshToken();
  if (!refreshToken) throw new ApiError(401, "authentication_required", "Not logged in.");

  const res = await fetch(`${API_BASE}/api/auth/refresh`, {
    method: "POST",
    headers: { Authorization: `Bearer ${refreshToken}` },
  });
  if (!res.ok) {
    clearTokens();
    throw new ApiError(401, "authentication_required", "Session expired.");
  }
  const body = await res.json();
  setAccessToken(body.access_token);
  return body.access_token;
}

async function request(path, { method = "GET", body, isForm = false, auth = true, retry = true } = {}) {
  const headers = {};
  if (!isForm) headers["Content-Type"] = "application/json";
  if (auth) {
    const token = getAccessToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: isForm ? body : body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (networkErr) {
    throw new ApiError(0, "network_error", "Can't reach Billio right now. Check your connection and try again.");
  }

  if (res.status === 401 && auth && retry) {
    try {
      await doRefresh();
      return request(path, { method, body, isForm, auth, retry: false });
    } catch {
      clearTokens();
      window.dispatchEvent(new CustomEvent("billio:logout"));
      throw new ApiError(401, "authentication_required", "Please log in again.");
    }
  }

  let payload = null;
  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    payload = await res.json().catch(() => null);
  }

  if (!res.ok) {
    const err = payload?.error || {};
    throw new ApiError(res.status, err.code || "unknown_error", err.message || "Something went wrong.", err.details);
  }

  return payload ?? (await res.blob());
}

export const api = {
  auth: {
    signup: (data) => request("/api/auth/signup", { method: "POST", body: data, auth: false }),
    login: (data) => request("/api/auth/login", { method: "POST", body: data, auth: false }),
    logout: () => request("/api/auth/logout", { method: "POST" }),
    me: () => request("/api/auth/me"),
    updateMe: (data) => request("/api/auth/me", { method: "PATCH", body: data }),
    changePassword: (data) => request("/api/auth/change-password", { method: "POST", body: data }),
    forgotPassword: (data) => request("/api/auth/forgot-password", { method: "POST", body: data, auth: false }),
    resetPassword: (data) => request("/api/auth/reset-password", { method: "POST", body: data, auth: false }),
    requestEmailVerification: () => request("/api/auth/verify-email/request", { method: "POST" }),
    confirmEmailVerification: (data) => request("/api/auth/verify-email/confirm", { method: "POST", body: data, auth: false }),
  },
  bills: {
    list: (status = "active") => request(`/api/bills?status=${status}`),
    create: (data) => request("/api/bills", { method: "POST", body: data }),
    get: (id) => request(`/api/bills/${id}`),
    update: (id, data) => request(`/api/bills/${id}`, { method: "PATCH", body: data }),
    cancel: (id) => request(`/api/bills/${id}`, { method: "DELETE" }),
  },
  occurrences: {
    list: (params = {}) => {
      const qs = new URLSearchParams(params).toString();
      return request(`/api/occurrences${qs ? `?${qs}` : ""}`);
    },
    get: (id) => request(`/api/occurrences/${id}`),
    markPaid: (id) => request(`/api/occurrences/${id}/mark-paid`, { method: "POST" }),
  },
  dashboard: {
    get: () => request("/api/dashboard"),
  },
  history: {
    list: (params = {}) => {
      const qs = new URLSearchParams(params).toString();
      return request(`/api/history${qs ? `?${qs}` : ""}`);
    },
    months: () => request("/api/history/months"),
    summary: (month) => request(`/api/history/summary?month=${month}`),
  },
  settings: {
    get: () => request("/api/settings"),
    update: (data) => request("/api/settings", { method: "PATCH", body: data }),
  },
  account: {
    exportCsv: () => request("/api/account/export"),
    delete: (password) => request("/api/account", { method: "DELETE", body: { password } }),
  },
  ai: {
    extractBill: (formData) => request("/api/ai/extract-bill", { method: "POST", body: formData, isForm: true }),
    extractBillsBatch: (formData) => request("/api/ai/extract-bills-batch", { method: "POST", body: formData, isForm: true }),
    parseText: (description) => request("/api/ai/parse-text", { method: "POST", body: { description } }),
    assistant: (message, history) => request("/api/ai/assistant", { method: "POST", body: { message, history } }),
    audit: (data) => request("/api/ai/audit", { method: "POST", body: data }),
  },
  documents: {
    get: (id) => request(`/api/documents/${id}`),
    downloadUrl: (id) => request(`/api/documents/${id}/download-url`),
  },
  notifications: {
    vapidPublicKey: () => request("/api/notifications/vapid-public-key", { auth: false }),
    subscribe: (subscription) => request("/api/notifications/push-subscription", { method: "POST", body: subscription }),
    unsubscribe: (endpoint) => request("/api/notifications/push-subscription", { method: "DELETE", body: { endpoint } }),
  },
  feedback: {
    submit: (data) => request("/api/feedback", { method: "POST", body: data }),
    mine: () => request("/api/feedback"),
  },
  admin: {
    listFeedback: (params = {}) => {
      const qs = new URLSearchParams(params).toString();
      return request(`/api/admin/feedback${qs ? `?${qs}` : ""}`);
    },
    getFeedback: (id) => request(`/api/admin/feedback/${id}`),
    updateFeedback: (id, data) => request(`/api/admin/feedback/${id}`, { method: "PATCH", body: data }),
  },
};

export { API_BASE };
