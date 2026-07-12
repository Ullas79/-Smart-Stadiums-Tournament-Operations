import { useEffect, useState } from "react";
import { RoleSwitcher } from "./components/RoleSwitcher";
import { ChatPanel } from "./components/ChatPanel";
import { OpsDashboard } from "./components/OpsDashboard";
import { ScenarioPanel } from "./components/ScenarioPanel";
import { fetchState } from "./api";
import type { Role, StadiumSnapshot } from "./types";
import "./App.css";

const LANGUAGES = ["en", "es", "pt", "fr", "ar", "zh", "ja", "de", "it"];

export default function App() {
  const [role, setRole] = useState<Role>("fan");
  const [language, setLanguage] = useState("en");
  const [snapshot, setSnapshot] = useState<StadiumSnapshot | null>(null);

  useEffect(() => {
    let active = true;
    async function poll() {
      try {
        const s = await fetchState();
        if (active) {
          setSnapshot((prev) => {
            // Avoid triggering re-render if snapshot data is identical
            if (JSON.stringify(prev) === JSON.stringify(s)) {
              return prev;
            }
            return s;
          });
        }
      } catch {
        /* backend not up yet */
      }
    }
    poll();
    const id = setInterval(poll, 1500);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  return (
    <div className="app">
      <header className="app-header">
        <h1><span aria-hidden="true">🏟️</span> Smart Stadiums Assistant</h1>
        <p className="subtitle">FIFA World Cup 2026 Final · MetLife Stadium</p>
      </header>

      <div className="app-controls">
        <RoleSwitcher role={role} onChange={setRole} />
        <label className="lang-picker">
          Language
          <select value={language} onChange={(e) => setLanguage(e.target.value)}>
            {LANGUAGES.map((l) => (
              <option key={l} value={l}>
                {l}
              </option>
            ))}
          </select>
        </label>
      </div>

      <main className="app-main">
        <div className="app-chat">
          <ChatPanel role={role} language={language} />
        </div>
        <div className="app-dashboard">
          <ScenarioPanel />
          <OpsDashboard snapshot={snapshot} />
        </div>
      </main>
    </div>
  );
}
