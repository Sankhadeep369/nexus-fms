// Turn an event { title, date "YYYY-MM-DD", time "HH:MM"|null, notes } into a Google
// Calendar "add event" link and a downloadable .ics (Outlook/Teams/Apple). Pure
// client-side — no backend, no external scripts.

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

function pad(n) {
  return String(n).padStart(2, "0");
}

// All-day (1 day) when no time; otherwise a 1-hour block.
function eventRange({ date, time }) {
  const [y, m, d] = date.split("-").map(Number);
  if (time) {
    const [hh, mm] = time.split(":").map(Number);
    const start = new Date(y, m - 1, d, hh, mm);
    return { start, end: new Date(start.getTime() + 3600000), allDay: false };
  }
  const start = new Date(y, m - 1, d);
  return { start, end: new Date(start.getTime() + 86400000), allDay: true };
}

function stamp(dt, allDay) {
  if (allDay) return `${dt.getFullYear()}${pad(dt.getMonth() + 1)}${pad(dt.getDate())}`;
  return dt.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
}

export function googleCalendarUrl(event) {
  const { start, end, allDay } = eventRange(event);
  const params = new URLSearchParams({
    action: "TEMPLATE",
    text: event.title || "Reminder",
    dates: `${stamp(start, allDay)}/${stamp(end, allDay)}`,
    details: event.notes || "",
  });
  return `https://calendar.google.com/calendar/render?${params.toString()}`;
}

function escapeIcs(s) {
  return String(s).replace(/([,;\\])/g, "\\$1").replace(/\n/g, "\\n");
}

export function downloadIcs(event) {
  const { start, end, allDay } = eventRange(event);
  const dtStart = allDay ? `DTSTART;VALUE=DATE:${stamp(start, true)}` : `DTSTART:${stamp(start, false)}`;
  const dtEnd = allDay ? `DTEND;VALUE=DATE:${stamp(end, true)}` : `DTEND:${stamp(end, false)}`;
  const ics = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//NEXUS//EN",
    "BEGIN:VEVENT",
    `UID:${Date.now()}@nexus`,
    `DTSTAMP:${stamp(new Date(), false)}`,
    dtStart,
    dtEnd,
    `SUMMARY:${escapeIcs(event.title || "Reminder")}`,
    `DESCRIPTION:${escapeIcs(event.notes || "")}`,
    "END:VEVENT",
    "END:VCALENDAR",
  ].join("\r\n");
  const url = URL.createObjectURL(new Blob([ics], { type: "text/calendar" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = `${(event.title || "event").replace(/[^\w-]+/g, "_").slice(0, 40)}.ics`;
  a.click();
  URL.revokeObjectURL(url);
}

// SLM-driven: ask the backend to extract an event from free-form text (a chat answer).
// Returns the event or null. Runs only on user click — never on the chat path.
export async function extractEvent(text) {
  try {
    const res = await fetch(`${API_BASE}/calendar/extract`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (!res.ok) return null;
    const d = await res.json();
    return d.found ? { title: d.title, date: d.date, time: d.time, notes: d.notes } : null;
  } catch {
    return null;
  }
}
