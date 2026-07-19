import { useEffect, useState } from "react";
import { Toaster } from "sonner";
import { useTranslation } from "react-i18next";
import { RoleSwitcher } from "./components/RoleSwitcher";
import { ChatPanel } from "./components/ChatPanel";
import { OpsDashboard } from "./components/OpsDashboard";
import { ScenarioPanel } from "./components/ScenarioPanel";
import { fetchState } from "./api";
import type { Role, StadiumSnapshot } from "./types";
import "./App.css";

export default function App() {
  const { t, i18n } = useTranslation();
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
            if (JSON.stringify(prev) === JSON.stringify(s)) return prev;
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

  const handleLanguageChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const lang = e.target.value;
    setLanguage(lang);
    i18n.changeLanguage(lang);
  };

  return (
    <div className="app">
      <Toaster theme="dark" position="top-right" />
      <header className="app-header">
        <div>
          <h1><span aria-hidden="true">🏟️</span> {t('title')}</h1>
          <p className="subtitle">{t('subtitle')}</p>
        </div>
        <div className="weather-widget" aria-label="Live stadium weather">
          <span className="weather-icon">🌤️</span> {t('weather')}
        </div>
      </header>

      <section className="app-controls" aria-label="Control panel">
        <RoleSwitcher role={role} onChange={setRole} />
        <label className="lang-picker" htmlFor="language-select">
          {t('language')}
          <select
            id="language-select"
            value={language}
            onChange={handleLanguageChange}
          >
            <option value="en">English</option>
            <option value="es">Español</option>
            <option value="fr">Français</option>
          </select>
        </label>
      </section>

      <main className={`app-main ${role === "fan" ? "fan-mode" : "ops-mode"}`}>
        <div className="app-chat">
          <ChatPanel key={role} role={role} language={language} />
        </div>
        {role !== "fan" && (
          <div className="app-dashboard">
            {role === "organizer" && <ScenarioPanel />}
            <OpsDashboard snapshot={snapshot} role={role} />
          </div>
        )}
      </main>
    </div>
  );
}
