/** Little cartoon characters for the playful themes. Original artwork. */
export default function Mascot({ kind, size = 56 }: { kind: "car" | "fish" | "fox"; size?: number }) {
  if (kind === "car") {
    return (
      <svg className="mascot" width={size * 1.5} height={size} viewBox="0 0 150 100" role="img" aria-label="A little purple car">
        <ellipse cx="75" cy="92" rx="58" ry="5" fill="#000" opacity=".15" />
        {/* body */}
        <path d="M12 62 Q12 40 34 38 L52 38 Q58 22 76 22 Q96 22 102 38 L120 40 Q140 44 140 62 L140 72 Q140 78 134 78 L18 78 Q12 78 12 72 Z"
          fill="#8a3fd1" stroke="#2b1245" strokeWidth="4" strokeLinejoin="round" />
        {/* window */}
        <path d="M58 38 Q63 28 76 28 Q90 28 95 38 Z" fill="#bfe9ff" stroke="#2b1245" strokeWidth="3.5" strokeLinejoin="round" />
        <path d="M70 31 L66 37" stroke="#fff" strokeWidth="3" strokeLinecap="round" opacity=".8" />
        {/* eyes as headlights */}
        <circle cx="112" cy="55" r="12" fill="#fff" stroke="#2b1245" strokeWidth="3.5" />
        <circle cx="115" cy="56" r="5.5" fill="#2b1245" />
        <circle cx="117" cy="54" r="1.8" fill="#fff" />
        {/* smile grille */}
        <path d="M118 70 Q130 74 138 66" fill="none" stroke="#2b1245" strokeWidth="3.5" strokeLinecap="round" />
        {/* stripe + bumper */}
        <path d="M14 66 L100 66" stroke="#ffcf3f" strokeWidth="4" strokeLinecap="round" />
        <rect x="132" y="68" width="12" height="7" rx="3" fill="#ffcf3f" stroke="#2b1245" strokeWidth="3" />
        {/* wheels */}
        {[38, 112].map((x) => (
          <g key={x} className="wheel" style={{ transformOrigin: `${x}px 80px` }}>
            <circle cx={x} cy="80" r="14" fill="#2b2b3a" stroke="#161621" strokeWidth="3" />
            <circle cx={x} cy="80" r="6" fill="#ddd" />
            <path d={`M${x - 9} 80 H${x + 9} M${x} 71 V89`} stroke="#9a9ab0" strokeWidth="2" />
          </g>
        ))}
      </svg>
    );
  }
  if (kind === "fox") {
    return (
      <svg className="mascot" width={size * 1.5} height={size} viewBox="0 0 150 100" role="img" aria-label="A friendly orange fox">
        <ellipse cx="72" cy="94" rx="52" ry="4.5" fill="#000" opacity=".15" />
        {/* bushy tail with a white tip */}
        <g className="tail" style={{ transformOrigin: "40px 58px" }}>
          <path d="M44 64 Q8 66 6 36 Q4 20 18 14 Q16 30 30 40 Q44 48 50 54 Z" fill="#f2711c" stroke="#4a2410" strokeWidth="3.5" strokeLinejoin="round" />
          <path d="M18 14 Q4 20 6 36 Q8 44 14 48 Q12 34 24 28 Q16 24 18 14 Z" fill="#fff6e8" stroke="#4a2410" strokeWidth="3" strokeLinejoin="round" />
        </g>
        {/* back legs and front legs */}
        <g className="leg" style={{ transformOrigin: "52px 70px" }}><path d="M46 68 L44 90 L58 90 L60 68 Z" fill="#f2711c" stroke="#4a2410" strokeWidth="3.5" strokeLinejoin="round" /><path d="M43 83 L44 90 L58 90 L59 83 Z" fill="#4a2410" /></g>
        <g className="leg l2" style={{ transformOrigin: "100px 70px" }}><path d="M92 68 L92 90 L106 90 L106 68 Z" fill="#f2711c" stroke="#4a2410" strokeWidth="3.5" strokeLinejoin="round" /><path d="M91 83 L92 90 L106 90 L107 83 Z" fill="#4a2410" /></g>
        {/* body */}
        <ellipse cx="74" cy="58" rx="40" ry="24" fill="#f2711c" stroke="#4a2410" strokeWidth="4" />
        <path d="M92 70 Q80 80 58 72 Q80 76 92 70 Z" fill="#fff6e8" />
        <path d="M98 50 Q112 62 100 76 Q92 70 92 60 Z" fill="#fff6e8" opacity=".95" />
        {/* head */}
        <path d="M96 30 L100 8 L112 24 Q122 22 132 28 L146 44 Q148 52 138 54 Q120 62 104 56 Q92 50 96 30 Z" fill="#f2711c" stroke="#4a2410" strokeWidth="4" strokeLinejoin="round" />
        <path d="M100 8 L104 22 L112 24 Z" fill="#4a2410" />
        <path d="M118 44 Q132 56 146 46 Q140 56 126 58 Q112 58 118 44 Z" fill="#fff6e8" />
        <ellipse cx="146" cy="45" rx="4.2" ry="3.4" fill="#2b1608" />
        <circle cx="120" cy="38" r="5.5" fill="#fff" stroke="#4a2410" strokeWidth="2.5" />
        <circle cx="122" cy="38.5" r="2.8" fill="#2b1608" /><circle cx="123" cy="37.3" r="1" fill="#fff" />
        <path d="M130 52 Q137 55 142 51" fill="none" stroke="#4a2410" strokeWidth="2.6" strokeLinecap="round" />
      </svg>
    );
  }
  return (
    <svg className="mascot" width={size * 1.5} height={size} viewBox="0 0 150 100" role="img" aria-label="A friendly yellow fish">
      {/* tail */}
      <path d="M26 50 L4 28 Q0 50 4 72 Z" fill="#ff9a2e" stroke="#7a3a00" strokeWidth="3.5" strokeLinejoin="round" className="tail" style={{ transformOrigin: "26px 50px" }} />
      {/* fins */}
      <path d="M62 24 Q76 6 92 24 Z" fill="#ff9a2e" stroke="#7a3a00" strokeWidth="3.5" strokeLinejoin="round" />
      <path d="M62 78 Q74 94 90 78 Z" fill="#ff9a2e" stroke="#7a3a00" strokeWidth="3.5" strokeLinejoin="round" />
      {/* body */}
      <ellipse cx="80" cy="51" rx="52" ry="31" fill="#ffd23f" stroke="#7a3a00" strokeWidth="4" />
      <path d="M52 26 Q46 51 52 76" fill="none" stroke="#ff9a2e" strokeWidth="5" strokeLinecap="round" opacity=".7" />
      {/* red pigtail ribbons */}
      <path d="M96 22 Q112 6 122 16 Q114 22 106 20" fill="#e5322d" stroke="#7a1010" strokeWidth="3" strokeLinejoin="round" />
      <path d="M100 78 Q116 94 126 84 Q118 78 110 80" fill="#e5322d" stroke="#7a1010" strokeWidth="3" strokeLinejoin="round" />
      {/* face */}
      <circle cx="108" cy="44" r="10" fill="#fff" stroke="#7a3a00" strokeWidth="3.5" />
      <circle cx="111" cy="45" r="5" fill="#1b2a4a" />
      <circle cx="113" cy="43" r="1.7" fill="#fff" />
      <path d="M110 62 Q122 68 130 58" fill="none" stroke="#7a3a00" strokeWidth="3.5" strokeLinecap="round" />
      <circle cx="98" cy="58" r="5" fill="#ff8a8a" opacity=".6" />
    </svg>
  );
}
