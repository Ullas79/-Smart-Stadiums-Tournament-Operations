import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import { ScenarioPanel } from "../components/ScenarioPanel";
import { triggerScenario } from "../api";

vi.mock("../api");
const mockedTriggerScenario = vi.mocked(triggerScenario);

test("renders scenario buttons and handles trigger click", async () => {
  mockedTriggerScenario.mockResolvedValue({
    status: "success",
    incident: {
      incident_id: "INC-SCENARIO-GATE-123",
      type: "entry_bottleneck",
      location: "Gate 2 (South Gate)",
      severity: "high",
      status: "active",
      description: "Gate 2 turnstile malfunction..."
    }
  });

  render(<ScenarioPanel />);

  // Verify elements are present
  expect(screen.getByText("Simulation Scenarios")).toBeInTheDocument();
  const gateBtn = screen.getByRole("button", { name: "Trigger gate malfunction scenario" });
  expect(gateBtn).toBeInTheDocument();

  // Click gate malfunction
  fireEvent.click(gateBtn);

  // Should display success message
  await waitFor(() =>
    expect(screen.getByText(/Triggered: gate malfunction. Incident spawned: Gate 2 \(South Gate\)/)).toBeInTheDocument()
  );

  expect(mockedTriggerScenario).toHaveBeenCalledWith("gate_malfunction");
});

test("handles reset click and displays success", async () => {
  mockedTriggerScenario.mockResolvedValue({
    status: "success",
    incident: null
  });

  render(<ScenarioPanel />);

  const resetBtn = screen.getByRole("button", { name: "Reset simulation to nominal" });
  fireEvent.click(resetBtn);

  await waitFor(() =>
    expect(screen.getByText(/All scenarios cleared and stadium states reset to nominal/)).toBeInTheDocument()
  );

  expect(mockedTriggerScenario).toHaveBeenCalledWith("reset");
});

test("displays error message on trigger failure", async () => {
  mockedTriggerScenario.mockRejectedValue(new Error("API failure"));

  render(<ScenarioPanel />);

  const medBtn = screen.getByRole("button", { name: "Trigger medical emergency scenario" });
  fireEvent.click(medBtn);

  await waitFor(() =>
    expect(screen.getByText(/API failure/)).toBeInTheDocument()
  );
});

