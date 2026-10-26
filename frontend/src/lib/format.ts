export function number(value: number | null | undefined, digits = 0) {
  return value == null
    ? "—"
    : new Intl.NumberFormat("en-GB", {
        maximumFractionDigits: digits,
        minimumFractionDigits: digits,
      }).format(value);
}
export function signed(value: number | null | undefined, digits = 0) {
  return value == null
    ? "—"
    : `${value > 0 ? "+" : ""}${number(value, digits)}`;
}
export function clock(value: string | null | undefined) {
  return value
    ? new Intl.DateTimeFormat("en-GB", {
        timeZone: "Europe/London",
        hour: "2-digit",
        minute: "2-digit",
      }).format(new Date(value))
    : "—";
}
export function dateLabel(value: string, short = false) {
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/London",
    day: "numeric",
    month: short ? "short" : "long",
    ...(!short ? { year: "numeric" as const } : {}),
  }).format(new Date(`${value.slice(0, 10)}T12:00:00Z`));
}
export function stamp(value: string | null | undefined) {
  return value
    ? new Intl.DateTimeFormat("en-GB", {
        timeZone: "Europe/London",
        day: "numeric",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
        timeZoneName: "short",
      }).format(new Date(value))
    : "Unavailable";
}
export function shiftDate(value: string, days: number) {
  const date = new Date(`${value}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}
