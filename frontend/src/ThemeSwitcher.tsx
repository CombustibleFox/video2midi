import { useEffect, useRef, useState } from "react";
import { THEMES, ThemeId, ThemeInfo } from "./themes";

export default function ThemeSwitcher({ theme, onChange }: { theme: ThemeInfo; onChange: (id: ThemeId) => void }) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const away = (e: MouseEvent) => !box.current?.contains(e.target as Node) && setOpen(false);
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", away);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);

  return (
    <div className="themes" ref={box}>
      <button type="button" className="theme-btn" aria-haspopup="listbox" aria-expanded={open} onClick={() => setOpen(!open)}>
        <Swatch colors={theme.swatch} /> <span>{theme.label}</span> <span aria-hidden="true">▾</span>
      </button>
      {open && (
        <ul className="theme-menu" role="listbox" aria-label="Theme">
          {THEMES.map((t) => (
            <li key={t.id} role="option" aria-selected={t.id === theme.id}>
              <button type="button" className={t.id === theme.id ? "on" : ""} onClick={() => { onChange(t.id); setOpen(false); }}>
                <Swatch colors={t.swatch} />
                <span><strong>{t.label}</strong><small>{t.blurb}</small></span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Swatch({ colors }: { colors: ThemeInfo["swatch"] }) {
  return (
    <span className="swatch" aria-hidden="true" style={{ background: colors[0] }}>
      <i style={{ background: colors[1] }} /><i style={{ background: colors[2] }} /><i style={{ background: colors[3] }} /><i style={{ background: colors[4] }} />
    </span>
  );
}
