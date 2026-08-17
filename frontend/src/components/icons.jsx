// Small, consistent line-icon set used throughout the app instead of
// emoji (which render inconsistently across platforms) -- keeps status
// communication legible and on-brand everywhere it appears.

const base = {
  fill: "none",
  strokeWidth: 2,
  strokeLinecap: "round",
  strokeLinejoin: "round",
};

export function CheckCircleIcon({ className = "h-5 w-5" }) {
  return (
    <svg viewBox="0 0 24 24" className={className} stroke="currentColor" {...base}>
      <circle cx="12" cy="12" r="9.25" />
      <path d="M8 12.5l2.5 2.5L16 9.5" />
    </svg>
  );
}

export function AlertTriangleIcon({ className = "h-5 w-5" }) {
  return (
    <svg viewBox="0 0 24 24" className={className} stroke="currentColor" {...base}>
      <path d="M12 3.5 21.5 20h-19L12 3.5Z" />
      <path d="M12 9.5v4.25" />
      <circle cx="12" cy="16.9" r="0.9" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function AlertCircleIcon({ className = "h-5 w-5" }) {
  return (
    <svg viewBox="0 0 24 24" className={className} stroke="currentColor" {...base}>
      <circle cx="12" cy="12" r="9.25" />
      <path d="M12 7.5v5.25" />
      <circle cx="12" cy="16.4" r="0.9" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function ClockIcon({ className = "h-5 w-5" }) {
  return (
    <svg viewBox="0 0 24 24" className={className} stroke="currentColor" {...base}>
      <circle cx="12" cy="12" r="9.25" />
      <path d="M12 7v5.25l3.5 2" />
    </svg>
  );
}

export function ChevronRightIcon({ className = "h-4 w-4" }) {
  return (
    <svg viewBox="0 0 24 24" className={className} stroke="currentColor" {...base}>
      <path d="M9 6l6 6-6 6" />
    </svg>
  );
}

export function PlusIcon({ className = "h-5 w-5" }) {
  return (
    <svg viewBox="0 0 24 24" className={className} stroke="currentColor" {...base}>
      <path d="M12 5v14M5 12h14" />
    </svg>
  );
}

export function CameraIcon({ className = "h-5 w-5" }) {
  return (
    <svg viewBox="0 0 24 24" className={className} stroke="currentColor" {...base}>
      <path d="M4 8.5a1.5 1.5 0 0 1 1.5-1.5h1.6l1-1.6h7.8l1 1.6h1.6A1.5 1.5 0 0 1 20 8.5v9A1.5 1.5 0 0 1 18.5 19h-13A1.5 1.5 0 0 1 4 17.5v-9Z" />
      <circle cx="12" cy="13" r="3.4" />
    </svg>
  );
}

export function SparkleIcon({ className = "h-5 w-5" }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor">
      <path d="M12 3l1.7 4.9L18.5 9.5 13.7 11.2 12 16.1 10.3 11.2 5.5 9.5 10.3 7.9 12 3Z" />
      <path d="M19 14l.75 2.1 2.1.75-2.1.75L19 19.6l-.75-2-2.1-.75 2.1-.75L19 14Z" />
    </svg>
  );
}

export function SendIcon({ className = "h-5 w-5" }) {
  return (
    <svg viewBox="0 0 24 24" className={className} stroke="currentColor" {...base}>
      <path d="M4.5 12 20 4.5 15 19.5l-3.6-6.4L4.5 12Z" />
    </svg>
  );
}

export function CloseIcon({ className = "h-5 w-5" }) {
  return (
    <svg viewBox="0 0 24 24" className={className} stroke="currentColor" {...base}>
      <path d="M6 6l12 12M18 6 6 18" />
    </svg>
  );
}

export function TrashIcon({ className = "h-5 w-5" }) {
  return (
    <svg viewBox="0 0 24 24" className={className} stroke="currentColor" {...base}>
      <path d="M4 7h16M9.5 7V5a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1v2M6.5 7l.8 12a1.5 1.5 0 0 0 1.5 1.4h6.4a1.5 1.5 0 0 0 1.5-1.4L17.5 7" />
    </svg>
  );
}

export function EditIcon({ className = "h-5 w-5" }) {
  return (
    <svg viewBox="0 0 24 24" className={className} stroke="currentColor" {...base}>
      <path d="M4 20h4l10.5-10.5a2 2 0 0 0 0-2.8l-1.2-1.2a2 2 0 0 0-2.8 0L4 16v4Z" />
    </svg>
  );
}

export function HomeIcon({ className = "h-5 w-5" }) {
  return (
    <svg viewBox="0 0 24 24" className={className} stroke="currentColor" {...base}>
      <path d="M4 11.5 12 4l8 7.5" />
      <path d="M6 10v9.5a1 1 0 0 0 1 1h3.5v-6h3v6H17a1 1 0 0 0 1-1V10" />
    </svg>
  );
}

export function ListIcon({ className = "h-5 w-5" }) {
  return (
    <svg viewBox="0 0 24 24" className={className} stroke="currentColor" {...base}>
      <path d="M9 6.5h11M9 12h11M9 17.5h11" />
      <circle cx="4.5" cy="6.5" r="1" fill="currentColor" stroke="none" />
      <circle cx="4.5" cy="12" r="1" fill="currentColor" stroke="none" />
      <circle cx="4.5" cy="17.5" r="1" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function GearIcon({ className = "h-5 w-5" }) {
  return (
    <svg viewBox="0 0 24 24" className={className} stroke="currentColor" {...base}>
      <circle cx="12" cy="12" r="3.2" />
      <path d="M12 3.5v2.3M12 18.2v2.3M20.5 12h-2.3M5.8 12H3.5M17.8 6.2l-1.6 1.6M7.8 16.2l-1.6 1.6M17.8 17.8l-1.6-1.6M7.8 7.8 6.2 6.2" />
    </svg>
  );
}

export function ChatIcon({ className = "h-5 w-5" }) {
  return (
    <svg viewBox="0 0 24 24" className={className} stroke="currentColor" {...base}>
      <path d="M4 5.5h16v10.5H9l-4 3.5v-3.5H4z" />
    </svg>
  );
}

export function LogoutIcon({ className = "h-5 w-5" }) {
  return (
    <svg viewBox="0 0 24 24" className={className} stroke="currentColor" {...base}>
      <path d="M9 4H6a1.5 1.5 0 0 0-1.5 1.5v13A1.5 1.5 0 0 0 6 20h3M15 16l4-4-4-4M19 12H9" />
    </svg>
  );
}
