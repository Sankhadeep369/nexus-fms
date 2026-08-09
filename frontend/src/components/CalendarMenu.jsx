import { useEffect, useRef, useState } from "react";
import { downloadIcs, googleCalendarUrl } from "../lib/calendar";
import { CalendarIcon } from "./icons";

// `getEvent` returns an event object (or null) — synchronously for reminders
// (structured fields) or via the SLM extractor for a chat answer. The menu only
// resolves on click, so nothing runs on the chat response path.
export default function CalendarMenu({ getEvent, triggerClassName, label }) {
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState("idle"); // idle | loading | ready | none
  const [event, setEvent] = useState(null);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e) => ref.current && !ref.current.contains(e.target) && setOpen(false);
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  const toggle = async () => {
    if (open) {
      setOpen(false);
      return;
    }
    setOpen(true);
    setStatus("loading");
    const ev = await getEvent();
    if (ev) {
      setEvent(ev);
      setStatus("ready");
    } else {
      setStatus("none");
    }
  };

  return (
    <div className="relative inline-block" ref={ref}>
      <button
        type="button"
        onClick={toggle}
        title="Add to calendar"
        className={triggerClassName}
      >
        <CalendarIcon className="h-3.5 w-3.5" />
        {label}
      </button>

      {open && (
        <div className="absolute bottom-full left-0 z-50 mb-1.5 w-48 rounded-xl border border-nexus-border bg-nexus-panel p-1 shadow-lg">
          {status === "loading" && (
            <p className="px-2.5 py-2 text-xs text-nexus-muted">Finding the date…</p>
          )}
          {status === "none" && (
            <p className="px-2.5 py-2 text-xs text-nexus-muted">No date found to add.</p>
          )}
          {status === "ready" && event && (
            <>
              <p className="truncate px-2.5 pb-1 pt-1.5 text-[11px] text-nexus-muted">
                {event.title} · {event.date}
                {event.time ? ` ${event.time}` : ""}
              </p>
              <a
                href={googleCalendarUrl(event)}
                target="_blank"
                rel="noreferrer"
                onClick={() => setOpen(false)}
                className="block rounded-lg px-2.5 py-2 text-sm text-nexus-text transition-colors hover:bg-nexus-panel2"
              >
                Google Calendar
              </a>
              <button
                type="button"
                onClick={() => {
                  downloadIcs(event);
                  setOpen(false);
                }}
                className="block w-full rounded-lg px-2.5 py-2 text-left text-sm text-nexus-text transition-colors hover:bg-nexus-panel2"
              >
                Outlook / Teams (.ics)
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
