import { memo } from "react";
import type { Role } from "../types";
import { useTranslation } from "react-i18next";
import "./RoleSwitcher.css";

const ROLES: { value: Role; emoji: string }[] = [
  { value: "fan", emoji: "🎟️" },
  { value: "volunteer", emoji: "🦺" },
  { value: "organizer", emoji: "🎛️" },
  { value: "staff", emoji: "🛠️" },
];

interface Props {
  role: Role;
  onChange: (role: Role) => void;
}

export const RoleSwitcher = memo(function RoleSwitcher({ role, onChange }: Props) {
  const { t } = useTranslation();
  return (
    <div className="role-switcher" role="group" aria-label="Select role">
      {ROLES.map((r) => (
        <button
          key={r.value}
          className={`role-btn ${role === r.value ? "active" : ""}`}
          onClick={() => onChange(r.value)}
          aria-pressed={role === r.value}
        >
          <span aria-hidden="true">{r.emoji}</span> {t(r.value)}
        </button>
      ))}
    </div>
  );
});
