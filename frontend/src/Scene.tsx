import type { ThemeId } from "./themes";

/** Decorative scenery behind the page for the themes that have it. Purely visual. */
export default function Scene({ theme }: { theme: ThemeId }) {
  if (theme === "roadtrip") {
    return (
      <div className="scene" aria-hidden="true">
        <svg className="sun" viewBox="0 0 120 120" width="150" height="150">
          <g stroke="#ffb400" strokeWidth="6" strokeLinecap="round">
            {Array.from({ length: 12 }, (_, i) => {
              const a = (i * Math.PI) / 6;
              return <line key={i} x1={60 + Math.cos(a) * 38} y1={60 + Math.sin(a) * 38} x2={60 + Math.cos(a) * 54} y2={60 + Math.sin(a) * 54} />;
            })}
          </g>
          <circle cx="60" cy="60" r="30" fill="#ffd93b" stroke="#ff9d00" strokeWidth="5" />
          <circle cx="50" cy="55" r="4" fill="#7a4a00" /><circle cx="70" cy="55" r="4" fill="#7a4a00" />
          <path d="M48 68 Q60 78 72 68" fill="none" stroke="#7a4a00" strokeWidth="4" strokeLinecap="round" />
        </svg>
        {[{ t: "9%", s: 1, d: 0 }, { t: "22%", s: 0.7, d: -40 }, { t: "5%", s: 0.55, d: -75 }].map((c, i) => (
          <svg key={i} className="cloud" style={{ top: c.t, animationDelay: `${c.d}s`, transform: `scale(${c.s})` }} viewBox="0 0 200 80" width="220" height="88">
            <path d="M30 70 Q8 70 10 52 Q12 36 32 38 Q36 14 62 16 Q80 4 100 18 Q122 6 140 24 Q166 22 170 46 Q192 48 188 64 Q186 72 172 70 Z"
              fill="#fff" stroke="#9fd2ee" strokeWidth="4" strokeLinejoin="round" />
          </svg>
        ))}
        <svg className="hills" viewBox="0 0 1200 220" preserveAspectRatio="none">
          <path d="M0 120 Q150 30 320 100 T640 90 T960 80 T1200 110 V220 H0 Z" fill="#7bd36b" stroke="#2f8f3a" strokeWidth="4" />
          <path d="M0 170 Q200 100 420 160 T820 150 T1200 160 V220 H0 Z" fill="#4fbf55" stroke="#2f8f3a" strokeWidth="4" />
          <g>{[90, 260, 520, 780, 1010, 1130].map((x, i) => (
            <g key={x} transform={`translate(${x} ${150 + (i % 2) * 22})`}>
              <line x1="0" y1="0" x2="0" y2="22" stroke="#2f8f3a" strokeWidth="3" />
              {[0, 72, 144, 216, 288].map((a) => (
                <ellipse key={a} cx="0" cy="-9" rx="5" ry="9" fill={["#ff6f91", "#ffd93b", "#fff", "#ff9d3a", "#c58cff", "#ff6f91"][i]} stroke="#7a3a00" strokeWidth="1.5" transform={`rotate(${a})`} />
              ))}
              <circle r="4.5" cy="0" fill="#ffd93b" stroke="#7a3a00" strokeWidth="1.5" />
            </g>
          ))}</g>
        </svg>
      </div>
    );
  }
  if (theme === "seaside") {
    return (
      <div className="scene" aria-hidden="true">
        <div className="rays" />
        {Array.from({ length: 16 }, (_, i) => (
          <span key={i} className="bubble" style={{
            left: `${(i * 37 + 8) % 96}%`, width: 10 + ((i * 13) % 22), height: 10 + ((i * 13) % 22),
            animationDuration: `${9 + ((i * 7) % 9)}s`, animationDelay: `${-((i * 5) % 14)}s`,
          }} />
        ))}
        <svg className="seabed" viewBox="0 0 1200 200" preserveAspectRatio="none">
          <path d="M0 120 Q220 70 460 118 T900 108 T1200 120 V200 H0 Z" fill="#f2d48a" stroke="#c99a3a" strokeWidth="4" />
          {[60, 180, 640, 1010, 1120].map((x, i) => (
            <path key={x} className="weed" style={{ transformOrigin: `${x}px 130px`, animationDelay: `${-i * 0.7}s` }}
              d={`M${x} 130 Q${x - 18} 96 ${x} 70 Q${x + 18} 44 ${x} 14`} fill="none" stroke={["#2fa84f", "#1f8f4a", "#38b86a"][i % 3]} strokeWidth="9" strokeLinecap="round" />
          ))}
          <g transform="translate(830 128)"><path d="M0 -22 L6 -7 L22 -7 L9 3 L14 19 L0 9 L-14 19 L-9 3 L-22 -7 L-6 -7 Z" fill="#ff7a59" stroke="#8a2f18" strokeWidth="3" strokeLinejoin="round" /></g>
          <g transform="translate(330 140)"><path d="M-24 0 Q-24 -26 0 -26 Q24 -26 24 0 Z" fill="#ffb3c7" stroke="#b04a6a" strokeWidth="3" /><path d="M-14 0 Q0 -16 14 0" fill="none" stroke="#b04a6a" strokeWidth="3" /></g>
        </svg>
      </div>
    );
  }
  if (theme === "fox") {
    const leaf = ["#e8590c", "#f59f00", "#c92a2a", "#fcc419", "#d9480f"];
    return (
      <div className="scene" aria-hidden="true">
        <svg className="sun" viewBox="0 0 120 120" width="170" height="170" style={{ animation: "none", left: "5%", right: "auto", top: "9%" }}>
          <circle cx="60" cy="60" r="44" fill="#ffe3a3" opacity=".55" /><circle cx="60" cy="60" r="30" fill="#fff0c2" stroke="#ffb454" strokeWidth="4" />
        </svg>
        {Array.from({ length: 18 }, (_, i) => (
          <span key={i} className="leaf" style={{
            left: `${(i * 29 + 5) % 100}%`, background: leaf[i % leaf.length],
            width: 12 + ((i * 7) % 12), height: 12 + ((i * 7) % 12),
            animationDuration: `${11 + ((i * 5) % 10)}s`, animationDelay: `${-((i * 3) % 16)}s`,
          }} />
        ))}
        <svg className="hills" viewBox="0 0 1200 260" preserveAspectRatio="none" style={{ height: "30vh" }}>
          <path d="M0 130 Q200 60 420 120 T820 100 T1200 120 V260 H0 Z" fill="#d98b4a" stroke="#7a3d12" strokeWidth="4" />
          {[110, 330, 560, 900, 1090].map((x, i) => (
            <g key={x} transform={`translate(${x} ${96 + (i % 2) * 20})`}>
              <rect x="-6" y="0" width="12" height="46" rx="3" fill="#7a3d12" />
              <circle cx="0" cy="-8" r="34" fill={leaf[i % leaf.length]} stroke="#7a3d12" strokeWidth="4" />
              <circle cx="-22" cy="8" r="22" fill={leaf[(i + 2) % leaf.length]} stroke="#7a3d12" strokeWidth="4" />
              <circle cx="22" cy="10" r="20" fill={leaf[(i + 1) % leaf.length]} stroke="#7a3d12" strokeWidth="4" />
            </g>
          ))}
          <path d="M0 190 Q260 130 520 186 T1200 170 V260 H0 Z" fill="#a8541d" stroke="#5d2a0a" strokeWidth="4" />
          {[220, 700, 1000].map((x) => (
            <g key={x} transform={`translate(${x} 188)`}>
              <path d="M0 0 Q-16 -18 -12 -34 Q0 -22 0 0 Q0 -22 12 -34 Q16 -18 0 0" fill="#fff6e8" stroke="#5d2a0a" strokeWidth="3" />
              <ellipse cx="0" cy="-8" rx="14" ry="9" fill="#e8c9a0" stroke="#5d2a0a" strokeWidth="3" />
            </g>
          ))}
        </svg>
      </div>
    );
  }
  return null;
}
