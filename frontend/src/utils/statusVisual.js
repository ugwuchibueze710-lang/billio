// Single source of truth for how a bill occurrence's status maps to color,
// icon, and copy across the app -- the core "green = done, normal = coming
// up, amber = approaching, red = needs attention" mental model.
import { CheckCircleIcon, AlertTriangleIcon, AlertCircleIcon, ClockIcon } from "../components/icons";

export function statusVisual(occurrence) {
  const { status, urgency_level } = occurrence;

  if (status === "paid") {
    return {
      icon: CheckCircleIcon,
      badgeClass: "bg-good-100 text-good-700",
      cardClass: "border-ink-100 bg-white",
      accentBar: "bg-good-500",
      dot: "bg-good-500",
    };
  }
  if (status === "overdue") {
    return {
      icon: AlertCircleIcon,
      badgeClass: "bg-danger-100 text-danger-700",
      cardClass: "border-danger-200 bg-danger-50/60 ring-1 ring-danger-100",
      accentBar: "bg-danger-600",
      dot: "bg-danger-600",
    };
  }
  if (status === "due_today") {
    return {
      icon: AlertTriangleIcon,
      badgeClass: "bg-danger-100 text-danger-700",
      cardClass: "border-danger-200 bg-white ring-1 ring-danger-100",
      accentBar: "bg-danger-500",
      dot: "bg-danger-500",
    };
  }
  if (urgency_level >= 1) {
    // approaching (due tomorrow / within 3 days)
    return {
      icon: ClockIcon,
      badgeClass: "bg-warn-100 text-warn-700",
      cardClass: "border-warn-200 bg-white",
      accentBar: "bg-warn-500",
      dot: "bg-warn-500",
    };
  }
  return {
    icon: ClockIcon,
    badgeClass: "bg-ink-100 text-ink-600",
    cardClass: "border-ink-100 bg-white",
    accentBar: "bg-ink-200",
    dot: "bg-ink-300",
  };
}
