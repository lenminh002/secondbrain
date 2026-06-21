import React from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";
import App from "./App";
import { AuthProvider } from "@/lib/auth";

const rootElement = document.getElementById("root");

if (!rootElement) {
  throw new Error("Root element #root was not found.");
}

createRoot(rootElement).render(
  <React.StrictMode>
    <AuthProvider>
      <App />
    </AuthProvider>
  </React.StrictMode>,
);
