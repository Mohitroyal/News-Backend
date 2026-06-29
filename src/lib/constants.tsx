

export const TEMPLATES_LIST = [
  {
    id: "bharath_reporter" as const,
    name: "Bharath Reporter",
    description: "Traditional Royal Broadsheet",
    accent: "from-green-600 to-orange-500",
    themeName: "Heritage Green & Saffron",
    tag: "National Heritage",
    textColor: "text-green-500",
    bgColor: "bg-white",
    borderColor: "border-[#15a850]/30",
    colors: ["#15a850", "#f28e1c", "#ffffff"],
    icon: (
      <svg viewBox="0 0 100 35" className="w-full h-full">
        <rect x="2" y="2" width="96" height="31" fill="none" stroke="#15a850" strokeWidth="0.8" />
        <rect x="3.5" y="3.5" width="93" height="28" fill="none" stroke="#f28e1c" strokeWidth="0.3" />
        <text x="6" y="7" fontSize="2" fill="#cc3333" fontWeight="bold" fontFamily="sans-serif">LICENCE No: HDP/010</text>
        <text x="6" y="22" fontSize="16" fontWeight="bold" fill="#15a850" stroke="#000" strokeWidth="0.3" fontFamily="serif">భారత్</text>
        <g transform="translate(6, 25)">
          <rect x="0" y="0" width="45" height="5" fill="#f28e1c" />
          <text x="2" y="3.5" fontSize="2.8" fontWeight="bold" fill="#ffffff" fontFamily="sans-serif">BHARATH REPORTER</text>
          
          <rect x="46" y="0" width="40" height="5" fill="#15a850" />
          <text x="66" y="3.5" fontSize="2.8" fontWeight="bold" fill="#ffffff" textAnchor="middle" fontFamily="sans-serif">రిపోర్టర్</text>
        </g>
      </svg>
    )
  },
  {
    id: "rti_express" as const,
    name: "RTI Express",
    description: "Fearless Investigative",
    accent: "from-blue-600 to-blue-800",
    themeName: "Investigative Royal Blue",
    tag: "Fearless Press",
    textColor: "text-blue-600",
    bgColor: "bg-white",
    borderColor: "border-[#1d70b8]/30",
    colors: ["#1d70b8", "#ffffff"],
    icon: (
      <svg viewBox="0 0 100 35" className="w-full h-full">
        <rect x="2" y="2" width="96" height="31" fill="none" stroke="#1d70b8" strokeWidth="0.8" />
        <rect x="3.2" y="3.2" width="93.6" height="28.6" fill="none" stroke="#1d70b8" strokeWidth="0.3" />
        
        <g transform="translate(6, 5)">
          <rect x="0" y="2" width="12" height="18" fill="none" stroke="#1d70b8" strokeWidth="0.8" />
          <rect x="3" y="5" width="12" height="18" fill="#ffffff" stroke="#1d70b8" strokeWidth="0.8" />
          <circle cx="9" cy="11" r="2.5" fill="#1d70b8" />
          <rect x="8.2" y="11" width="1.6" height="7" fill="#1d70b8" />
        </g>
        
        <text x="25" y="16" fontSize="12" fontWeight="bold" fill="#1d70b8" fontFamily="serif">RTI</text>
        <text x="25" y="26" fontSize="10.5" fontWeight="bold" fill="#1d70b8" fontFamily="serif">EXPRESS</text>
        
        <line x1="25" y1="29" x2="45" y2="29" stroke="#1d70b8" strokeWidth="0.3" />
        <text x="58" y="30.5" fontSize="3" fontStyle="italic" fontWeight="bold" fill="#1d70b8" textAnchor="middle" fontFamily="serif">Right to News</text>
        <line x1="71" y1="29" x2="92" y2="29" stroke="#1d70b8" strokeWidth="0.3" />
      </svg>
    )
  },
  {
    id: "national_news" as const,
    name: "National News Reporter",
    description: "Elite Global Journal",
    accent: "from-purple-600 to-indigo-800",
    themeName: "Imperial Purple & Crimson",
    tag: "Global Record",
    textColor: "text-purple-400",
    bgColor: "bg-[#761c9e]",
    borderColor: "border-[#761c9e]/40",
    colors: ["#761c9e", "#ffffff", "#cc2424", "#1b2e4b"],
    icon: (
      <svg viewBox="0 0 100 35" className="w-full h-full">
        <rect x="0" y="0" width="100" height="35" fill="#761c9e" />
        <rect x="1.5" y="1.5" width="97" height="32" fill="none" stroke="#ffffff" strokeWidth="0.4" />
        <rect x="2.5" y="2.5" width="95" height="30" fill="none" stroke="#000000" strokeWidth="0.3" />
        
        <text x="6" y="20" fontSize="12.5" fontWeight="bold" fill="#ffffff" fontFamily="serif">నేషనల్ న్యూస్</text>
        
        <g transform="translate(85, 23) rotate(-10)">
          <text x="0" y="0" fontSize="4.2" fontWeight="bold" fill="#ffffff" textAnchor="middle" fontFamily="sans-serif">రిపోర్టర్</text>
        </g>
        
        <g transform="translate(6, 23)">
          <rect x="0" y="0" width="70" height="8" fill="#ffffff" />
          <rect x="0.5" y="0.5" width="69" height="7" fill="#000000" />
          
          <rect x="1" y="1" width="43" height="6" fill="#cc2424" />
          <text x="3" y="5.2" fontSize="4.5" fontWeight="bold" fill="#ffffff" fontFamily="sans-serif">NATIONAL</text>
          
          <rect x="45" y="1" width="23" height="6" fill="#1b2e4b" />
          <text x="46" y="5.2" fontSize="4.5" fontWeight="bold" fill="#ffffff" fontFamily="sans-serif">NEWS</text>
        </g>
      </svg>
    )
  },
  {
    id: "hero-image" as const,
    name: "The Extra News",
    description: "Wrapped Inline Image Style",
    accent: "from-blue-500 to-blue-700",
    themeName: "Classic Blue Extra",
    tag: "Visual Wrap",
    textColor: "text-blue-500",
    bgColor: "bg-blue-600",
    borderColor: "border-blue-600/30",
    colors: ["#3b82f6", "#1e40af", "#ffffff"],
    icon: (
      <svg viewBox="0 0 100 35" className="w-full h-full">
        <rect x="0" y="0" width="100" height="35" fill="#3b82f6" />
        <text x="6" y="11" fontSize="6.5" fontStyle="italic" fontWeight="bold" fill="#ffffff" fontFamily="serif">THE</text>
        <text x="6" y="28" fontSize="17.5" fontWeight="900" fill="#ffffff" fontFamily="sans-serif" letterSpacing="0.8">EXTRA NEWS</text>
      </svg>
    )
  }
];
