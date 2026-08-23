// Tokens are stored in localStorage so a session survives a refresh/reopen
// of the browser -- standard practice for a header-based JWT SPA (the
// backend does not use cookies). Access tokens are short-lived (15 min)
// and every security-relevant event (password change, logout) bumps the
// server-side token_version, which instantly invalidates any token that
// leaks, independent of how it's stored client-side.
const ACCESS_KEY = "billio.access_token";
const REFRESH_KEY = "billio.refresh_token";

export function getAccessToken() {
  return localStorage.getItem(ACCESS_KEY);
}

export function getRefreshToken() {
  return localStorage.getItem(REFRESH_KEY);
}

export function setTokens({ access_token, refresh_token }) {
  if (access_token) localStorage.setItem(ACCESS_KEY, access_token);
  if (refresh_token) localStorage.setItem(REFRESH_KEY, refresh_token);
}

export function setAccessToken(token) {
  localStorage.setItem(ACCESS_KEY, token);
}

export function clearTokens() {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}
