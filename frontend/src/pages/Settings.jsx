import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { api, ApiError, API_BASE } from "../api/client";
import { useToast } from "../context/ToastContext";
import { subscribeToPush, unsubscribeFromPush, getPushPermissionState } from "../utils/push";
import { getAccessToken } from "../api/tokenStorage";

const REMINDER_FIELDS = [
  { key: "reminder_7_days", label: "7 days before" },
  { key: "reminder_3_days", label: "3 days before" },
  { key: "reminder_1_day", label: "1 day before" },
  { key: "reminder_due_today", label: "On the due date" },
  { key: "overdue_reminders", label: "When overdue (up to 3 days)" },
];

export default function Settings() {
  const { user, logout, refreshUser } = useAuth();
  const navigate = useNavigate();
  const { show } = useToast();
  const [settings, setSettings] = useState(null);
  const [pushState, setPushState] = useState("default");

  useEffect(() => {
    api.settings.get().then((r) => setSettings(r.settings));
    getPushPermissionState().then(setPushState);
  }, []);

  async function updateSetting(key, value) {
    setSettings((s) => ({ ...s, [key]: value }));
    try {
      await api.settings.update({ [key]: value });
    } catch (err) {
      show(err.message || "Couldn't save that setting.", { type: "error" });
    }
  }

  async function handleEnablePush() {
    try {
      await subscribeToPush();
      setPushState("granted");
      show("Push notifications enabled.", { type: "success" });
    } catch (err) {
      show(err.message, { type: "error" });
    }
  }

  async function handleDisablePush() {
    await unsubscribeFromPush();
    show("Push notifications disabled on this device.", { type: "success" });
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-ink-900">Settings</h1>
        <p className="text-sm text-ink-500">@{user.username}</p>
      </div>

      <ProfileSection user={user} refreshUser={refreshUser} show={show} />

      {settings && (
        <section className="rounded-2xl border border-ink-100 bg-white p-5">
          <h2 className="mb-3 font-bold text-ink-900">Notifications</h2>

          <div className="mb-4 space-y-3">
            <Toggle label="Push notifications" checked={settings.push_notifications} onChange={(v) => updateSetting("push_notifications", v)} />
            <Toggle label="Email reminders" checked={settings.email_notifications} onChange={(v) => updateSetting("email_notifications", v)} />
            <Toggle
              label="Private notification text"
              description="Hide bill name and amount on lock-screen notifications"
              checked={settings.private_notification_text}
              onChange={(v) => updateSetting("private_notification_text", v)}
            />
          </div>

          {settings.push_notifications && (
            <div className="mb-4 rounded-xl bg-ink-50 p-3">
              {pushState === "granted" ? (
                <button onClick={handleDisablePush} className="text-sm font-semibold text-danger-600">
                  Turn off push on this device
                </button>
              ) : (
                <button onClick={handleEnablePush} className="text-sm font-semibold text-brand-600">
                  Enable push on this device
                </button>
              )}
            </div>
          )}

          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-400">Remind me</p>
          <div className="space-y-2">
            {REMINDER_FIELDS.map((f) => (
              <Toggle key={f.key} label={f.label} checked={settings[f.key]} onChange={(v) => updateSetting(f.key, v)} compact />
            ))}
          </div>
        </section>
      )}

      {user.is_admin && (
        <Link to="/admin/feedback" className="block rounded-2xl border border-ink-100 bg-white p-5 font-semibold text-brand-600">
          Admin: Feedback dashboard →
        </Link>
      )}

      <AccountSection show={show} logout={logout} navigate={navigate} />
    </div>
  );
}

function Toggle({ label, description, checked, onChange, compact }) {
  return (
    <label className={`flex cursor-pointer items-center justify-between ${compact ? "py-0.5" : ""}`}>
      <div>
        <span className="text-sm font-medium text-ink-800">{label}</span>
        {description && <p className="text-xs text-ink-400">{description}</p>}
      </div>
      <button
        type="button"
        onClick={() => onChange(!checked)}
        className={`relative h-6 w-11 shrink-0 rounded-full transition ${checked ? "bg-brand-600" : "bg-ink-200"}`}
      >
        <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform ${checked ? "translate-x-5" : "translate-x-0.5"}`} />
      </button>
    </label>
  );
}

function ProfileSection({ user, refreshUser, show }) {
  const [email, setEmail] = useState(user.email || "");
  const [saving, setSaving] = useState(false);
  const [verifySent, setVerifySent] = useState(false);

  async function saveEmail() {
    setSaving(true);
    try {
      await api.auth.updateMe({ email: email || null });
      await refreshUser();
      show("Email updated.", { type: "success" });
    } catch (err) {
      show(err.message || "Couldn't update email.", { type: "error" });
    } finally {
      setSaving(false);
    }
  }

  async function sendVerification() {
    try {
      await api.auth.requestEmailVerification();
      setVerifySent(true);
      show("Verification email sent.", { type: "success" });
    } catch (err) {
      show(err.message || "Couldn't send verification email.", { type: "error" });
    }
  }

  return (
    <section className="rounded-2xl border border-ink-100 bg-white p-5">
      <h2 className="mb-3 font-bold text-ink-900">Profile</h2>
      <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-ink-400">
        Email <span className="normal-case text-ink-300">(optional)</span>
      </label>
      <div className="flex gap-2">
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@example.com"
          className="flex-1 rounded-xl border border-ink-200 px-3.5 py-2.5 text-sm outline-none focus:border-brand-400 focus:ring-2 focus:ring-brand-100"
        />
        <button onClick={saveEmail} disabled={saving} className="rounded-xl bg-ink-900 px-4 text-sm font-semibold text-white hover:bg-ink-800 disabled:opacity-50">
          Save
        </button>
      </div>
      {user.email && (
        <p className="mt-2 text-xs text-ink-500">
          {user.email && !verifySent ? (
            <>
              Status: <strong>unverified email needs a click to confirm</strong>.{" "}
              <button onClick={sendVerification} className="font-semibold text-brand-600 hover:underline">
                Resend verification
              </button>
            </>
          ) : verifySent ? (
            "Verification email sent — check your inbox."
          ) : null}
        </p>
      )}
    </section>
  );
}

function AccountSection({ show, logout, navigate }) {
  const [password, setPassword] = useState("");
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  async function handleExport() {
    try {
      const token = getAccessToken();
      const res = await fetch(`${API_BASE}/api/account/export`, { headers: { Authorization: `Bearer ${token}` } });
      if (!res.ok) throw new Error("Export failed.");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "billio-export.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      show("Couldn't export your data. Please try again.", { type: "error" });
    }
  }

  async function handleDelete() {
    try {
      await api.account.delete(password);
      show("Your account has been deleted.", { type: "success" });
      await logout();
      navigate("/login");
    } catch (err) {
      show(err instanceof ApiError ? err.message : "Couldn't delete account.", { type: "error" });
    }
  }

  return (
    <section className="space-y-3 rounded-2xl border border-ink-100 bg-white p-5">
      <h2 className="font-bold text-ink-900">Your data</h2>
      <button onClick={handleExport} className="w-full rounded-xl border border-ink-200 py-2.5 text-sm font-semibold text-ink-700 hover:bg-ink-50">
        Export all bills & history (CSV)
      </button>
      <button onClick={logout} className="w-full rounded-xl border border-ink-200 py-2.5 text-sm font-semibold text-ink-700 hover:bg-ink-50">
        Log out
      </button>

      {!confirmingDelete ? (
        <button onClick={() => setConfirmingDelete(true)} className="w-full rounded-xl border border-danger-200 py-2.5 text-sm font-semibold text-danger-600 hover:bg-danger-50">
          Delete account
        </button>
      ) : (
        <div className="rounded-xl border border-danger-200 bg-danger-50 p-4">
          <p className="mb-2 text-sm font-semibold text-danger-700">
            This permanently deletes your account and all bills, history, and documents. This cannot be undone.
          </p>
          <input
            type="password"
            placeholder="Confirm your password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mb-2 w-full rounded-xl border border-danger-200 px-3.5 py-2.5 text-sm outline-none"
          />
          <div className="flex gap-2">
            <button onClick={handleDelete} disabled={!password} className="flex-1 rounded-xl bg-danger-600 py-2.5 text-sm font-semibold text-white disabled:opacity-50">
              Permanently delete
            </button>
            <button onClick={() => setConfirmingDelete(false)} className="flex-1 rounded-xl border border-ink-200 py-2.5 text-sm font-semibold text-ink-600">
              Cancel
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
