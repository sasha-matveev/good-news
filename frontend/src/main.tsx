import React from "react";
import ReactDOM from "react-dom/client";

import { AppShell } from "./app/AppShell";
import { AuthGate } from "./app/AuthGate";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AuthGate>
      <AppShell />
    </AuthGate>
  </React.StrictMode>
);
