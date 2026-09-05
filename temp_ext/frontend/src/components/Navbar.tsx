import { Home, Radio, Plus, LayoutTemplate, Settings } from 'lucide-react';
import { useLocation, useNavigate } from 'react-router-dom';

const NAVY = '#0E2A4D';
const RED = '#C8202E';

export const Navbar = () => {
  const location = useLocation();
  const navigate = useNavigate();

  const navItems = [
    { name: 'Home', path: '/', icon: Home },
    { name: 'Feed', path: '/feed', icon: Radio },
    // Center placeholder for FAB
    { name: '', path: '', icon: null, isSpacer: true },
    { name: 'Templates', path: '/templates', icon: LayoutTemplate },
    { name: 'Settings', path: '/settings', icon: Settings },
  ];

  return (
    <div 
      className="fixed bottom-0 w-full h-16 flex items-center justify-around px-2 z-50 shadow-[0_-4px_20px_rgba(0,0,0,0.15)]"
      style={{ backgroundColor: NAVY }}
    >
      {navItems.map((item, index) => {
        if (item.isSpacer) {
          return <div key={index} className="w-16" />; // Spacer for FAB
        }

        const Icon = item.icon!;
        // Simple logic to match base path to highlight correctly
        const isActive = location.pathname === item.path || (item.path !== '/' && location.pathname.startsWith(item.path));

        return (
          <button
            key={item.name}
            onClick={() => navigate(item.path)}
            className="flex flex-col items-center justify-center w-16 h-full gap-1 active:scale-95 transition-transform"
          >
            <Icon 
              className={`w-[22px] h-[22px] transition-colors`} 
              style={{ color: isActive ? RED : '#8A99A8' }}
              strokeWidth={isActive ? 2.5 : 2}
            />
            <span 
              className={`text-[10px] font-medium transition-colors`}
              style={{ color: isActive ? RED : '#8A99A8' }}
            >
              {item.name}
            </span>
          </button>
        );
      })}

      {/* Center FAB Button */}
      <button
        onClick={() => navigate('/generate')}
        className="absolute -top-6 left-1/2 -translate-x-1/2 w-14 h-14 rounded-full flex items-center justify-center text-white shadow-xl active:scale-95 transition-transform"
        style={{ backgroundColor: RED, border: '3px solid white' }}
      >
        <Plus className="w-8 h-8" strokeWidth={3} />
      </button>
    </div>
  );
};
