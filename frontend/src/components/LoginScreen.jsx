import { useState } from "react";
import { useAppConfig } from "../context/AppConfigContext";
import { useAuth } from "../context/AuthContext";
import { LogoIcon } from "./icons";

export default function LoginScreen() {
  const { login } = useAuth();
  const { brandName } = useAppConfig();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(false);

  const submit = (e) => {
    e.preventDefault();
    if (!login(username, password)) setError(true);
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-nexus-bg px-4">
      <div className="aurora" aria-hidden="true" />
      <form onSubmit={submit} className="relative z-10 w-full max-w-sm rounded-2xl border border-nexus-border bg-nexus-panel/80 p-6 shadow-glow backdrop-blur-sm">
        <div className="mb-5 flex flex-col items-center text-center">
          <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-nexus-accent to-nexus-accent2 text-nexus-bg shadow-glow-sm">
            <LogoIcon className="h-6 w-6" />
          </span>
          <h1 className="mt-3 font-display text-lg font-semibold text-nexus-text">Sign in to {brandName}</h1>
          <p className="mt-1 text-xs text-nexus-muted">Facilities-management assistant</p>
        </div>

        <label className="block text-xs text-nexus-muted">
          Username
          <input
            value={username}
            onChange={(e) => {
              setUsername(e.target.value);
              setError(false);
            }}
            autoFocus
            className="mt-1 w-full rounded-xl border border-nexus-border bg-nexus-bg px-3 py-2 text-sm text-nexus-text focus:border-nexus-accent/60 focus:outline-none"
          />
        </label>
        <label className="mt-3 block text-xs text-nexus-muted">
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
              setError(false);
            }}
            className="mt-1 w-full rounded-xl border border-nexus-border bg-nexus-bg px-3 py-2 text-sm text-nexus-text focus:border-nexus-accent/60 focus:outline-none"
          />
        </label>

        {error && <p className="mt-3 text-xs text-red-400">Incorrect username or password.</p>}

        <button
          type="submit"
          className="mt-5 w-full rounded-xl bg-gradient-to-br from-nexus-accent to-nexus-accent2 px-4 py-2.5 text-sm font-medium text-nexus-bg transition-all hover:shadow-glow-sm active:scale-95"
        >
          Sign in
        </button>
      </form>
    </div>
  );
}
