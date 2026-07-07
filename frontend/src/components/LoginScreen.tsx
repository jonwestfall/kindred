import { FormEvent, useState } from "react";

import { api, authToken } from "../api";
import type { SessionInfo } from "../types";
import { Icon } from "./Icon";

export function LoginScreen({ onLogin }: { onLogin: (session: SessionInfo) => void }) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const result = await api.auth.login(username, password);
      authToken.set(result.token);
      onLogin(result.session);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Login failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="login-screen">
      <form className="login-card" onSubmit={submit}>
        <div className="login-mark">
          <Icon name="feather" size={30} />
        </div>
        <h1>Kindred</h1>
        <p>Sign in to your local character home.</p>
        <label className="field">
          <span>Username</span>
          <input
            autoComplete="username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            required
          />
        </label>
        <label className="field">
          <span>Password</span>
          <input
            autoComplete="current-password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </label>
        {error ? <p className="form-error">{error}</p> : null}
        <button className="primary-button" disabled={loading}>
          {loading ? "Signing in…" : "Sign in"}
        </button>
        <small>
          The first administrator username and password come from your <code>.env</code> file.
        </small>
      </form>
    </main>
  );
}
