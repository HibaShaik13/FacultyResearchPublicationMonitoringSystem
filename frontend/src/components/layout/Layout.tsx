import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { 
  LogOut, 
  LayoutDashboard, 
  User, 
  FileText, 
  CheckSquare, 
  TrendingUp, 
  ShieldAlert, 
  Search, 
  Network, 
  Bot, 
  FileBarChart, 
  Bell, 
  Settings as SettingsIcon, 
  Menu,
  CheckCheck,
  ChevronRight,
  AlertTriangle,
  CheckCircle,
  Sparkles,
  Activity,
  Sun,
  ChevronDown
} from 'lucide-react';
import { useState, useEffect, useRef } from 'react';
import api from '../../services/api';

const sidebarSections = [
  {
    title: "MY RESEARCH",
    items: [
      { path: '/', label: 'Dashboard', icon: <LayoutDashboard size={18} /> },
      { path: '/profile', label: 'My Profile', icon: <User size={18} /> },
      { path: '/publications', label: 'My Publications', icon: <FileText size={18} /> },
      { path: '/verification', label: 'Verification Queue', icon: <CheckSquare size={18} /> },
      { path: '/impact', label: 'Research Impact', icon: <TrendingUp size={18} /> },
      { path: '/integrity', label: 'Research Integrity', icon: <ShieldAlert size={18} /> },
    ]
  },
  {
    title: "EXPLORE",
    items: [
      { path: '/search', label: 'Research Search', icon: <Search size={18} /> },
      { path: '/areas', label: 'Research Areas', icon: <FileText size={18} /> },
      { path: '/collaborations', label: 'Collaborations', icon: <Network size={18} /> },
      { path: '/opportunities', label: 'Opportunities', icon: <Network size={18} /> },
    ]
  },
  {
    title: "INTELLIGENCE",
    items: [
      { path: '/pipeline', label: 'Research Pipeline', icon: <Bot size={18} /> },
      { path: '/graph', label: 'Knowledge Graph', icon: <Network size={18} /> },
      { path: '/assistant', label: 'Research Assistant', icon: <Bot size={18} /> },
    ]
  },
  {
    title: "REPORTS",
    items: [
      { path: '/reports', label: 'Reports', icon: <FileBarChart size={18} /> },
      { path: '/analytics', label: 'Analytics', icon: <TrendingUp size={18} /> },
    ]
  },
  {
    title: "SYSTEM",
    items: [
      { path: '/monitoring', label: 'System Monitoring', icon: <Activity size={18} /> },
      { path: '/notifications', label: 'Notifications', icon: <Bell size={18} /> },
      { path: '/settings', label: 'Settings', icon: <SettingsIcon size={18} /> },
    ]
  }
];

interface QuickNotification {
  id: string;
  title: string;
  message: string;
  severity: string;
  category: string;
  is_read: boolean;
  action_url?: string;
  created_at?: string;
}

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [unreadCount, setUnreadCount] = useState<number>(3);
  const [showNotifs, setShowNotifs] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [recentNotifs, setRecentNotifs] = useState<QuickNotification[]>([]);
  const notifDropdownRef = useRef<HTMLDivElement>(null);
  const userMenuRef = useRef<HTMLDivElement>(null);

  const fetchUnreadCount = async () => {
    try {
      const res = await api.get('/api/v1/notifications/unread-count');
      if (typeof res.data.unread_count === 'number') {
        setUnreadCount(res.data.unread_count);
      }
    } catch {
      // Ignore unauthenticated or offline errors
    }
  };

  const fetchRecentNotifications = async () => {
    try {
      const res = await api.get('/api/v1/notifications/?limit=5');
      setRecentNotifs(res.data.data || []);
      if (typeof res.data.unread_count === 'number') {
        setUnreadCount(res.data.unread_count);
      }
    } catch {
      // Ignore
    }
  };

  useEffect(() => {
    fetchUnreadCount();
    const interval = setInterval(fetchUnreadCount, 20000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (showNotifs) {
      fetchRecentNotifications();
    }
  }, [showNotifs]);

  // Click outside to close dropdowns
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (notifDropdownRef.current && !notifDropdownRef.current.contains(event.target as Node)) {
        setShowNotifs(false);
      }
      if (userMenuRef.current && !userMenuRef.current.contains(event.target as Node)) {
        setShowUserMenu(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const handleNotificationClick = async (notif: QuickNotification) => {
    setShowNotifs(false);
    if (!notif.is_read) {
      try {
        await api.post(`/api/v1/notifications/${notif.id}/read`);
        setUnreadCount(prev => Math.max(0, prev - 1));
      } catch {
        // Ignore
      }
    }
    if (notif.action_url) {
      navigate(notif.action_url);
    } else {
      navigate('/notifications');
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await api.post('/api/v1/notifications/read-all');
      setUnreadCount(0);
      setRecentNotifs(prev => prev.map(n => ({ ...n, is_read: true })));
    } catch {
      // Ignore
    }
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      navigate(`/search?q=${encodeURIComponent(searchQuery.trim())}`);
    }
  };

  const getUserInitials = (name?: string) => {
    if (!name) return 'DK';
    const parts = name.trim().split(/\s+/).filter(Boolean);
    if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  };

  const getUserSubtitle = () => {
    if (!user) return 'Faculty | CSE';
    if (user.role === 'research_admin' || user.role === 'super_admin') return 'Research Admin';
    return 'Faculty | CSE';
  };

  return (
    <div className="h-screen flex flex-col bg-[#f8fafc] font-sans antialiased overflow-hidden selection:bg-blue-500 selection:text-white">
      {/* ============================================================ */}
      {/* TIER 1: TOP BANNER (Ultra-Sharp Native Typography & High-Res)*/}
      {/* ============================================================ */}
      <div className="w-full h-16 sm:h-[72px] bg-gradient-to-r from-[#eef4fe] via-[#e2edfe] to-[#e8f1fd] border-b border-blue-200/70 shrink-0 select-none relative overflow-hidden px-4 sm:px-8 shadow-xs z-30 flex items-center justify-between">
        {/* Background Campus Panorama with smooth gradient fade masks */}
        <div 
          className="absolute inset-y-0 right-28 sm:right-36 md:right-48 w-3/5 max-w-2xl bg-cover sm:bg-contain bg-right bg-no-repeat pointer-events-none opacity-90 hidden sm:block"
          style={{
            backgroundImage: `url('/vignan_banner_campus_clean.png')`,
            maskImage: 'linear-gradient(to right, transparent 0%, black 15%, black 85%, transparent 100%)',
            WebkitMaskImage: 'linear-gradient(to right, transparent 0%, black 15%, black 85%, transparent 100%)',
          }}
        />

        {/* Left: High-Resolution Vignan Official Logo + Slogan Header */}
        <div className="relative z-10 flex items-center gap-4 sm:gap-6">
          <NavLink to="/" title="Vignan's Foundation for Science, Technology & Research" className="flex items-center">
            <img 
              src="/vignan_logo_clean_hd.png" 
              alt="Vignan's Foundation for Science, Technology & Research" 
              className="h-10 sm:h-12 w-auto object-contain drop-shadow-2xs"
            />
          </NavLink>

          {/* Vertical Divider */}
          <div className="hidden lg:block w-[1px] h-9 bg-blue-300/80 mx-1"></div>

          {/* University Slogan Header (Native Razor-Sharp Vector Text) */}
          <div className="hidden lg:flex flex-col justify-center">
            <h2 className="text-base sm:text-lg font-black text-slate-900 leading-tight">
              Research for a <span className="text-[#3b5bf5]">Better Tomorrow</span>
            </h2>
            <p className="text-[11px] font-semibold text-slate-500 tracking-wide mt-0.5">
              Discover &nbsp;•&nbsp; Verify &nbsp;•&nbsp; Analyze &nbsp;•&nbsp; Advance
            </p>
          </div>
        </div>

        {/* Right: Slogan Script (Crisp Vector Typography) */}
        <div className="relative z-10 text-right pr-2 sm:pr-4 hidden md:block">
          <div className="font-serif italic text-blue-950/85 text-base sm:text-lg font-semibold leading-tight tracking-wide select-none drop-shadow-[0_1px_1px_rgba(255,255,255,0.8)]">
            <div>Innovate</div>
            <div>Integrate</div>
            <div>Impact</div>
          </div>
        </div>
      </div>

      {/* ============================================================ */}
      {/* TIER 2 & TIER 3: SIDEBAR AS BEFORE + MAIN CONTENT WITH HEADER*/}
      {/* ============================================================ */}
      <div className="flex-1 flex min-h-0 overflow-hidden relative">
        {/* Sidebar Navigation (Restored Exactly as Before) */}
        <aside 
          className={`${
            sidebarOpen ? 'w-64' : 'w-20'
          } flex-shrink-0 transition-all duration-300 flex flex-col border-r border-white/10 z-40 sidebar-bg shadow-xl`}
        >
          {/* Sidebar Top: NAVIGATION Header */}
          <div className="h-14 flex items-center justify-between px-4 border-b border-white/10 shrink-0">
            {sidebarOpen ? (
              <span className="text-xs font-black tracking-wider text-white/90 uppercase px-1">Navigation</span>
            ) : (
              <div className="w-7 h-7 rounded-full bg-blue-800 text-white font-bold flex items-center justify-center mx-auto text-xs">V</div>
            )}
            <button 
              onClick={() => setSidebarOpen(!sidebarOpen)} 
              className="text-gray-400 hover:text-white p-1 rounded-lg hover:bg-white/5 transition-colors"
              title={sidebarOpen ? "Collapse Sidebar" : "Expand Sidebar"}
            >
              <Menu size={18} />
            </button>
          </div>

          {/* Sidebar Items (With Dashboard under MY RESEARCH as before) */}
          <div className="flex-1 overflow-y-auto py-3 custom-scrollbar">
            {sidebarSections.map((section, idx) => (
              <div key={idx} className="mb-4">
                {sidebarOpen && (
                  <p className="px-4 text-[11px] font-bold text-gray-400 mb-1.5 uppercase tracking-wider">
                    {section.title}
                  </p>
                )}
                <ul className="space-y-0.5">
                  {section.items.map((item) => (
                    <li key={item.path}>
                      <NavLink
                        to={item.path}
                        end={item.path === '/'}
                        className={({ isActive }) =>
                          `flex items-center gap-3 px-4 py-2 mx-2 rounded-xl transition-all ${
                            isActive 
                              ? 'bg-blue-600 text-white shadow-md shadow-blue-600/30 font-semibold' 
                              : 'text-gray-300 hover:bg-white/10 hover:text-white font-medium'
                          }`
                        }
                        title={!sidebarOpen ? item.label : undefined}
                      >
                        <span className="flex-shrink-0 relative">
                          {item.icon}
                          {item.path === '/notifications' && unreadCount > 0 && (
                            <span className="absolute -top-1 -right-1 w-2 h-2 bg-red-500 rounded-full"></span>
                          )}
                        </span>
                        {sidebarOpen && (
                          <span className="text-xs sm:text-sm font-medium whitespace-nowrap flex items-center justify-between w-full">
                            <span className="truncate">{item.label}</span>
                            {item.path === '/notifications' && unreadCount > 0 && (
                              <span className="ml-auto text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-red-500 text-white">
                                {unreadCount}
                              </span>
                            )}
                          </span>
                        )}
                      </NavLink>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </aside>

        {/* Main Content Area with Top Design Header */}
        <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden bg-[#f8fafc]">
          {/* ============================================================ */}
          {/* TOP DESIGN BAR: SEARCH & USER ACTIONS (Kept as user praised) */}
          {/* ============================================================ */}
          <header className="h-14 sm:h-15 flex items-center justify-between px-4 sm:px-6 border-b border-blue-200/70 bg-gradient-to-r from-[#eaf2fc] via-[#f0f6fd] to-[#edf4fc] shrink-0 z-20 shadow-xs">
            {/* Search Input Box */}
            <form onSubmit={handleSearchSubmit} className="flex-1 max-w-xl sm:max-w-2xl">
              <div className="relative flex items-center">
                <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-blue-500/75 pointer-events-none" />
                <input 
                  type="text" 
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search publications, researchers, topics, journals..."
                  className="w-full bg-white/95 hover:bg-white focus:bg-white border border-blue-200/80 rounded-xl pl-10 pr-4 py-1.5 text-xs sm:text-sm text-slate-800 placeholder:text-slate-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-100 outline-none transition-all shadow-2xs"
                />
              </div>
            </form>

            {/* Right Action Icons: Notifications, Sun Toggle, Divider, User Avatar */}
            <div className="flex items-center gap-3 sm:gap-4 shrink-0 ml-4">
              {/* Notification Bell with Badge */}
              <div className="relative" ref={notifDropdownRef}>
                <button 
                  onClick={() => setShowNotifs(!showNotifs)}
                  className="relative p-1.5 text-slate-600 hover:text-blue-600 hover:bg-blue-100/50 rounded-lg transition-colors flex items-center justify-center"
                  title="Notifications"
                >
                  <Bell size={20} className="text-slate-700" />
                  <span className="absolute -top-1.5 -right-1.5 min-w-4 h-4 px-1 bg-[#e53e3e] text-white text-[10px] font-black flex items-center justify-center rounded-full shadow-xs">
                    {unreadCount > 99 ? '99+' : unreadCount || '3'}
                  </span>
                </button>

                {/* Notification Popover Dropdown */}
                {showNotifs && (
                  <div className="absolute right-0 mt-2 w-80 sm:w-96 bg-white rounded-2xl shadow-2xl border border-gray-200 py-2 z-50 animate-in fade-in slide-in-from-top-2 duration-150">
                    <div className="flex items-center justify-between px-4 py-2.5 border-b border-gray-100">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-sm text-gray-900">Notifications</span>
                        {unreadCount > 0 && (
                          <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-blue-100 text-blue-700">
                            {unreadCount} new
                          </span>
                        )}
                      </div>
                      {unreadCount > 0 && (
                        <button
                          onClick={handleMarkAllRead}
                          className="text-xs text-blue-600 hover:text-blue-800 font-semibold flex items-center gap-1"
                        >
                          <CheckCheck size={14} /> Mark all read
                        </button>
                      )}
                    </div>

                    <div className="max-h-80 overflow-y-auto divide-y divide-gray-50 custom-scrollbar">
                      {recentNotifs.length === 0 ? (
                        <div className="p-6 text-center text-gray-500">
                          <Bell size={24} className="mx-auto text-gray-300 mb-2" />
                          <p className="text-xs font-semibold">No new research monitoring events</p>
                        </div>
                      ) : (
                        recentNotifs.map(n => (
                          <div
                            key={n.id}
                            onClick={() => handleNotificationClick(n)}
                            className={`p-3.5 hover:bg-blue-50/50 cursor-pointer transition-colors flex items-start gap-3 ${
                              !n.is_read ? 'bg-blue-50/20' : ''
                            }`}
                          >
                            <div className="p-1.5 rounded-lg bg-gray-50 mt-0.5 shrink-0">
                              {n.severity === 'critical' ? (
                                <ShieldAlert size={16} className="text-red-500" />
                              ) : n.severity === 'warning' ? (
                                <AlertTriangle size={16} className="text-amber-500" />
                              ) : n.severity === 'success' ? (
                                <CheckCircle size={16} className="text-emerald-500" />
                              ) : (
                                <Sparkles size={16} className="text-blue-500" />
                              )}
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center justify-between gap-1 mb-0.5">
                                <p className="text-xs font-bold text-gray-900 truncate">{n.title}</p>
                                {!n.is_read && <span className="w-1.5 h-1.5 rounded-full bg-blue-600 shrink-0"></span>}
                              </div>
                              <p className="text-[11px] text-gray-600 line-clamp-2 leading-relaxed">{n.message}</p>
                              <span className="text-[10px] text-gray-400 mt-1 block">
                                {n.created_at ? new Date(n.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Just now'}
                              </span>
                            </div>
                          </div>
                        ))
                      )}
                    </div>

                    <div className="px-3 pt-2 pb-1 border-t border-gray-100 text-center">
                      <button
                        onClick={() => {
                          setShowNotifs(false);
                          navigate('/notifications');
                        }}
                        className="w-full py-1.5 text-xs font-bold text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded-xl transition-colors flex items-center justify-center gap-1"
                      >
                        <span>View All Notifications</span>
                        <ChevronRight size={14} />
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* Sun Toggle Icon (Day/Night Theme Toggle) */}
              <button 
                type="button"
                className="p-1.5 text-slate-600 hover:text-amber-500 hover:bg-blue-100/50 rounded-lg transition-colors flex items-center justify-center"
                title="Toggle Day/Night Mode"
              >
                <Sun size={19} className="text-slate-700" />
              </button>

              {/* Vertical Divider */}
              <div className="h-5 w-[1px] bg-slate-300 mx-0.5"></div>

              {/* User Profile Widget (Avatar DK + Name + Subtitle + Chevron) */}
              <div className="relative" ref={userMenuRef}>
                <div 
                  onClick={() => setShowUserMenu(!showUserMenu)}
                  className="flex items-center gap-2.5 py-1 px-1.5 rounded-xl hover:bg-blue-100/50 transition-colors cursor-pointer group"
                >
                  {/* Dark Navy Circle Avatar with Initials */}
                  <div className="w-8 h-8 rounded-full bg-[#0a1633] text-white flex items-center justify-center font-bold text-xs shadow-xs ring-1 ring-blue-900/40">
                    {getUserInitials(user?.full_name)}
                  </div>
                  
                  {/* Stacked User Name & Role */}
                  <div className="text-left hidden md:block">
                    <p className="text-xs font-bold text-slate-900 group-hover:text-blue-700 transition-colors leading-tight">
                      {user?.full_name || 'Dr. Sarah Khan'}
                    </p>
                    <p className="text-[10.5px] font-medium text-slate-500 leading-tight mt-0.5">
                      {getUserSubtitle()}
                    </p>
                  </div>

                  <ChevronDown size={14} className="text-slate-500 group-hover:text-slate-700 transition-colors" />
                </div>

                {/* User Dropdown Menu */}
                {showUserMenu && (
                  <div className="absolute right-0 mt-2 w-56 bg-white rounded-2xl shadow-2xl border border-gray-200 py-2 z-50 animate-in fade-in slide-in-from-top-2 duration-150">
                    <div className="px-4 py-3 border-b border-gray-100">
                      <p className="text-xs font-bold text-gray-900">{user?.full_name || 'Dr. Sarah Khan'}</p>
                      <p className="text-[11px] text-gray-500 truncate">{user?.email || 'faculty@vignan.ac.in'}</p>
                      <span className="mt-1.5 inline-block px-2 py-0.5 bg-blue-100 text-blue-700 text-[9px] font-bold rounded-full uppercase tracking-wider">
                        {user ? user.role.replace('_', ' ') : 'Faculty'}
                      </span>
                    </div>

                    <div className="py-1">
                      <button
                        onClick={() => {
                          setShowUserMenu(false);
                          navigate('/profile');
                        }}
                        className="w-full px-4 py-2 text-left text-xs font-medium text-gray-700 hover:bg-blue-50 hover:text-blue-700 transition-colors flex items-center gap-2"
                      >
                        <User size={14} /> My Profile
                      </button>
                      <button
                        onClick={() => {
                          setShowUserMenu(false);
                          navigate('/settings');
                        }}
                        className="w-full px-4 py-2 text-left text-xs font-medium text-gray-700 hover:bg-blue-50 hover:text-blue-700 transition-colors flex items-center gap-2"
                      >
                        <SettingsIcon size={14} /> Settings
                      </button>
                    </div>

                    <div className="pt-1 border-t border-gray-100">
                      <button
                        onClick={handleLogout}
                        className="w-full px-4 py-2 text-left text-xs font-bold text-red-600 hover:bg-red-50 transition-colors flex items-center gap-2"
                      >
                        <LogOut size={14} /> Sign Out
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </header>

          {/* Main Route Content */}
          <main className="flex-1 overflow-y-auto p-6 relative bg-[#f8fafc]">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  );
}
