// Sign-in page: one box for any access code; the server decides the role (operator, evaluator, field team).
import "@fontsource/inter/latin-400.css";
import "@fontsource/inter/latin-500.css";
import "@fontsource/space-grotesk/latin-500.css";
import "./styles/tokens.css";
import "./styles/login.css";
import { mountIcons } from "./icons.js";

mountIcons();
const $ = (id) => document.getElementById(id);
const next = new URLSearchParams(location.search).get("next") || "";

$("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("go").disabled = true;
  $("msg").textContent = "";
  try {
    const r = await fetch("/auth/login", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code: $("code").value, next }),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.detail || `HTTP ${r.status}`);
    location.replace(data.next);  // the server only ever returns a path on this laptop
  } catch (err) {
    $("msg").textContent = err.message === "Failed to fetch" ? "The Typhon laptop is not reachable on this network." : err.message;
    $("code").select();
  } finally {
    $("go").disabled = false;
  }
});
