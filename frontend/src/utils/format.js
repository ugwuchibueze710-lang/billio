export function formatMoney(value) {
  const n = typeof value === "string" ? parseFloat(value) : value;
  if (Number.isNaN(n)) return "$0.00";
  return n.toLocaleString("en-US", { style: "currency", currency: "USD" });
}

export function formatShortDate(isoDate) {
  if (!isoDate) return "";
  const d = new Date(`${isoDate}T00:00:00`);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export function formatMonthLabel(monthStr) {
  // monthStr like "2026-08"
  const [year, month] = monthStr.split("-").map(Number);
  const d = new Date(year, month - 1, 1);
  return d.toLocaleDateString("en-US", { month: "long", year: "numeric" });
}

export function categoryLabel(category) {
  if (!category) return "Uncategorized";
  return category
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export const CATEGORIES = [
  "utilities",
  "housing",
  "insurance",
  "entertainment",
  "phone",
  "internet",
  "subscription",
  "transportation",
  "health",
  "debt",
  "other",
];

export const RECURRENCE_LABELS = {
  none: "One-time",
  weekly: "Weekly",
  monthly: "Monthly",
  quarterly: "Quarterly",
  yearly: "Yearly",
};

// Index 0 = January, matching the 1-12 "month" values the backend uses for
// annual bills (see app/services/recurrence.resolve_annual_due_date) --
// index + 1 is the value sent to the API.
export const MONTH_LABELS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];
