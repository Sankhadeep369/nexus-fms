import { createContext, useContext, useMemo, useState } from "react";

// Optional, local-only profile. Nothing is sent to a server — this just lets a
// user personalise the app (name shown in the sidebar) and have their email
// pre-filled for the Reminder Agent. Account creation is never enforced.
const STORAGE_KEY = "nexus-profile";

const ProfileContext = createContext(null);

function load() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const p = raw ? JSON.parse(raw) : null;
    return p && p.name ? p : null;
  } catch {
    return null;
  }
}

export function ProfileProvider({ children }) {
  const [profile, setProfile] = useState(load);

  const value = useMemo(
    () => ({
      profile,
      saveProfile: ({ name, email }) => {
        const clean = { name: (name || "").trim(), email: (email || "").trim() };
        if (!clean.name) return;
        localStorage.setItem(STORAGE_KEY, JSON.stringify(clean));
        setProfile(clean);
      },
      signOut: () => {
        localStorage.removeItem(STORAGE_KEY);
        setProfile(null);
      },
    }),
    [profile]
  );

  return <ProfileContext.Provider value={value}>{children}</ProfileContext.Provider>;
}

export function useProfile() {
  return useContext(ProfileContext);
}

// Stable id used to scope a user's uploaded documents (retrieval owner). Uses the
// profile email when set, otherwise a per-device guest id so uploads stay separate
// per browser even without an account.
export function ownerId(profile) {
  if (profile?.email) return profile.email.trim().toLowerCase();
  let g = localStorage.getItem("nexus-guest-id");
  if (!g) {
    g = "guest-" + Math.random().toString(36).slice(2, 10);
    localStorage.setItem("nexus-guest-id", g);
  }
  return g;
}

export function initials(name) {
  const parts = (name || "").trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}
