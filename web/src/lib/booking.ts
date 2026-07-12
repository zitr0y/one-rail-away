export function localDate(offsetDays = 0, now = new Date()): string {
  const date = new Date(now);
  date.setDate(date.getDate() + offsetDays);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function dateStamp(date: string): number {
  const [year, month, day] = date.split("-").map(Number);
  return Date.UTC(year, month - 1, day);
}

export function shiftDate(date: string, offsetDays: number): string {
  return localDate(offsetDays, new Date(`${date}T12:00:00`));
}

export function friendlyDateLabel(date: string, today = localDate()): string {
  const difference = (dateStamp(date) - dateStamp(today)) / (24 * 60 * 60 * 1000);
  if (difference === 0) return "Today";
  if (difference === 1) return "Tomorrow";
  return new Intl.DateTimeFormat("en-GB", { weekday: "short", day: "numeric", month: "short" })
    .format(new Date(`${date}T12:00:00`)).replace(",", "");
}

export function bookingUrl(): string {
  return "https://www.thetrainline.com/";
}
