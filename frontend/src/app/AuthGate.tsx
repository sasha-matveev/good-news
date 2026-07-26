import { useEffect, useState, type ReactNode } from "react";
import type { User } from "firebase/auth";

import { signInWithGoogle, watchUser } from "../lib/firebase";
import { theme } from "../styles/theme";

export function AuthGate({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => watchUser(setUser), []);

  if (user === undefined) {
    return (
      <main style={{ fontFamily: theme.font.body, padding: "4rem", textAlign: "center" }}>
        Loading…
      </main>
    );
  }

  if (!user) {
    return (
      <main style={{ fontFamily: theme.font.body, padding: "4rem", textAlign: "center" }}>
        <h1>Good News</h1>
        <p>Sign in to read your feed.</p>
        <button
          type="button"
          onClick={() => {
            setError(null);
            signInWithGoogle().catch((exc: unknown) => {
              setError(exc instanceof Error ? exc.message : String(exc));
            });
          }}
          style={{ fontSize: "1rem", padding: "0.6rem 1.4rem", cursor: "pointer" }}
        >
          Sign in with Google
        </button>
        {error ? <p style={{ color: "crimson" }}>{error}</p> : null}
      </main>
    );
  }

  return <>{children}</>;
}
