import { useCallback, useEffect, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export function useReminders(email) {
  const [reminders, setReminders] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const refresh = useCallback(() => {
    if (!email) return;
    setLoading(true);
    setError(null);
    fetch(`${API_BASE}/agents/reminders?email=${encodeURIComponent(email)}`)
      .then((res) => (res.ok ? res.json() : Promise.reject(res)))
      .then((data) => setReminders(data))
      .catch(() => setError("Couldn't load reminders. Is the Reminder Agent configured?"))
      .finally(() => setLoading(false));
  }, [email]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const createReminder = useCallback(
    async ({ title, dueDate, dueTime, system, notes, relatedVendor }) => {
      const res = await fetch(`${API_BASE}/agents/reminders`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title,
          due_date: dueDate,
          due_time: dueTime || null,
          system: system || null,
          recipient_email: email,
          notes: notes || null,
          related_vendor: relatedVendor || null,
        }),
      });
      if (!res.ok) throw new Error("Failed to create reminder");
      refresh();
    },
    [email, refresh]
  );

  const updateReminder = useCallback(
    async (id, { title, dueDate, dueTime, system, notes, relatedVendor }) => {
      const res = await fetch(`${API_BASE}/agents/reminders/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title,
          due_date: dueDate,
          due_time: dueTime || null,
          system: system || null,
          notes: notes || null,
          related_vendor: relatedVendor || null,
        }),
      });
      if (!res.ok) throw new Error("Failed to update reminder");
      refresh();
    },
    [refresh]
  );

  const cancelReminder = useCallback(
    async (id) => {
      const res = await fetch(`${API_BASE}/agents/reminders/${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error("Failed to cancel reminder");
      refresh();
    },
    [refresh]
  );

  return { reminders, loading, error, createReminder, updateReminder, cancelReminder, refresh };
}
