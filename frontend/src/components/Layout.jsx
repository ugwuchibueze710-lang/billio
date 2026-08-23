import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import FeedbackBar from "./FeedbackBar";
import { HomeIcon, ListIcon, PlusIcon, ChatIcon, GearIcon } from "./icons";

const NAV_ITEMS = [
  { to: "/", label: "Home", icon: HomeIcon, end: true },
  { to: "/history", label: "History", icon: ListIcon },
  { to: "/bills/new", label: "Add", icon: PlusIcon, primary: true },
  { to: "/assistant", label: "Assistant", icon: ChatIcon },
  { to: "/settings", label: "Settings", icon: GearIcon },
];

export default function Layout() {
  const { user } = useAuth();

  return (
    <div className="min-h-screen bg-ink-50 pb-24">
      <header className="sticky top-0 z-30 border-b border-ink-100 bg-ink-50/90 backdrop-blur">
        <div className="mx-auto flex max-w-2xl items-center justify-between px-4 py-3.5 sm:px-6">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-ink-900 text-sm font-bold text-white">B</div>
            <span className="text-lg font-bold tracking-tight text-ink-900">Billio</span>
          </div>
          {user && (
            <NavLink to="/settings" className="text-sm font-medium text-ink-500 hover:text-ink-900">
              Hi, {user.first_name}
            </NavLink>
          )}
        </div>
      </header>

      <main className="mx-auto max-w-2xl px-4 py-6 sm:px-6">
        <Outlet />
      </main>

      {user && <FeedbackBar />}

      <nav className="fixed inset-x-0 bottom-0 z-40 border-t border-ink-100 bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-2xl items-stretch justify-between px-2 sm:px-6">
          {NAV_ITEMS.map(({ to, label, icon: Icon, end, primary }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex flex-1 flex-col items-center gap-1 py-2.5 text-[11px] font-medium transition ${
                  primary
                    ? "relative"
                    : isActive
                    ? "text-brand-600"
                    : "text-ink-400 hover:text-ink-600"
                }`
              }
            >
              {({ isActive }) =>
                primary ? (
                  <>
                    <span className="flex h-11 w-11 -translate-y-3 items-center justify-center rounded-full bg-brand-600 text-white shadow-lg shadow-brand-600/30">
                      <Icon className="h-5 w-5" />
                    </span>
                    <span className="-mt-2 text-ink-400">{label}</span>
                  </>
                ) : (
                  <>
                    <Icon className="h-5 w-5" />
                    {label}
                  </>
                )
              }
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  );
}
