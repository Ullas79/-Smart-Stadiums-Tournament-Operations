import { useState, useCallback, memo } from "react";
import { triggerScenario } from "../api";
import "./ScenarioPanel.css";

export const ScenarioPanel = memo(function ScenarioPanel() {
  const [loading, setLoading] = useState(false);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);

  const handleTrigger = useCallback(async (scenario: string) => {
    setLoading(true);
    setFeedback(null);
    try {
      const res = await triggerScenario(scenario);
      if (res.status === "success") {
        if (scenario === "reset") {
          setFeedback({
            type: "success",
            message: "All scenarios cleared and stadium states reset to nominal.",
          });
        } else {
          setFeedback({
            type: "success",
            message: `Triggered: ${scenario.replace("_", " ")}. Incident spawned: ${res.incident?.location ?? "Unknown"}.`,
          });
        }
      } else {
        setFeedback({
          type: "error",
          message: "Failed to trigger scenario.",
        });
      }
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      setFeedback({
        type: "error",
        message: error.message || "Failed to trigger scenario.",
      });
    } finally {
      setLoading(false);
    }
  }, []);

  return (
    <section className="scenario-panel" aria-label="Scenario Injection Panel">
      <h3>Simulation Scenarios</h3>
      <div className="scenario-buttons">
        <button
          className="scenario-btn danger-border"
          disabled={loading}
          onClick={async () => {
            await handleTrigger("gate_malfunction");
          }}
          title="Simulate turnstile malfunction at South Gate"
          aria-label="Trigger gate malfunction scenario"
        >
          <span aria-hidden="true">🚨</span> Gate Malfunction
        </button>
        <button
          className="scenario-btn danger-border"
          disabled={loading}
          onClick={async () => {
            await handleTrigger("medical_emergency");
          }}
          title="Simulate medical emergency in Section 104"
          aria-label="Trigger medical emergency scenario"
        >
          <span aria-hidden="true">🚑</span> Medical Emergency
        </button>
        <button
          className="scenario-btn warning-border"
          disabled={loading}
          onClick={async () => {
            await handleTrigger("concession_surge");
          }}
          title="Simulate crowd surge at Club North Concourse"
          aria-label="Trigger concession surge scenario"
        >
          <span aria-hidden="true">🍔</span> Concession Surge
        </button>
        <button
          className="scenario-btn reset-btn"
          disabled={loading}
          onClick={async () => {
            await handleTrigger("reset");
          }}
          title="Reset stadium parameters and clear active incidents"
          aria-label="Reset simulation to nominal"
        >
          <span aria-hidden="true">🔄</span> Reset State
        </button>
      </div>
      {feedback && (
        <div className={`feedback-message ${feedback.type}`}>
          {feedback.message}
        </div>
      )}
    </section>
  );
});
