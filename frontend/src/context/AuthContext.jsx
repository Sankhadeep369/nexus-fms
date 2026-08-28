import { createContext, useContext, useMemo, useState } from "react";
import { currentUser, login as doLogin, logout as doLogout } from "../lib/auth";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => currentUser());

  const value = useMemo(
    () => ({
      user,
      isAdmin: user?.role === "admin",
      login: (u, p) => {
        const res = doLogin(u, p);
        if (res) setUser(res);
        return res;
      },
      logout: () => {
        doLogout();
        setUser(null);
      },
      // Re-read the session after the admin edits the logged-in user's own access.
      refresh: () => setUser(currentUser()),
      canTool: (id) => (user?.role === "admin" ? true : Boolean(user?.perms?.tools?.[id])),
      canAgent: (id) => (user?.role === "admin" ? true : Boolean(user?.perms?.agents?.[id])),
      reminderPerms: user?.perms?.reminder ?? { create: false, manage: false },
    }),
    [user]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
