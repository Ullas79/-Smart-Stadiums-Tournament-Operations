import { render, screen, fireEvent } from "@testing-library/react";
import { RoleSwitcher } from "../components/RoleSwitcher";
import type { Role } from "../types";

test("renders all four roles and marks the active one", () => {
  let role: Role = "fan";
  render(<RoleSwitcher role={role} onChange={(r) => (role = r)} />);
  expect(screen.getByText("Fan")).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByText("Volunteer")).toHaveAttribute("aria-pressed", "false");
  expect(screen.getByText("Organizer")).toBeInTheDocument();
  expect(screen.getByText("Staff")).toHaveAttribute("aria-pressed", "false");
});

test("clicking a role calls onChange", () => {
  let role: Role = "fan";
  render(<RoleSwitcher role={role} onChange={(r) => (role = r)} />);
  fireEvent.click(screen.getByText("Organizer"));
  expect(role).toBe("organizer");

  fireEvent.click(screen.getByText("Staff"));
  expect(role).toBe("staff");
});
