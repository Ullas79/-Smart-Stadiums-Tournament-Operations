import type { Role } from "../types";
import "./RoleSwitcher.css";

const ROLES: { value: Role; label: string; emoji: string }[] = [
  { value: "fan", label: "Fan", emoji: "🎟️" },
  { value: "volunteer", label: "Volunteer", emoji: "🦺" },
  { value: "organizer", label: "Organizer", emoji: "🎛️" },
];

interface Props {
  role: Role;
  onChange: (role: Role) => void;
}

export function RoleSwitcher({ role, onChange }: Props) {
  return (
    <div className="role-switcher" role="group" aria-label="Select role">
      {ROLES.map((r) => (
        <button
          key={r.value}
          className={`role-btn ${role === r.value ? "active" : ""}`}
          onClick={() => onChange(r.value)}
          aria-pressed={role === r.value}
        >
          <span aria-hidden="true">{r.emoji}</span> {r.label}
        </button>
      ))}
    </div>
  );
}
