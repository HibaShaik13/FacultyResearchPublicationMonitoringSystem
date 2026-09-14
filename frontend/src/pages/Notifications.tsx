import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';
import { 
  Bell, 
  CheckCheck, 
  ShieldAlert, 
  CheckCircle, 
  AlertTriangle, 
  Info, 
  FileText, 
  ExternalLink, 
  RotateCw, 
  Bot, 
  Sparkles, 
  Search
} from 'lucide-react';

interface NotificationItem {
  id: string;
  title: string;
  message: string;
  notification_type: string;
  category: string;
  severity: 'info' | 'warning' | 'critical' | 'success';
  entity_type?: string;
  entity_id?: string;
  source_agent?: string;
  source_event?: string;
  action_url?: string;
  is_read: boolean;
  read_at?: string;
  created_at?: string;
  event_metadata?: Record<string, any>;
}

interface NotificationSummary {
  unread: number;
  critical: number;
  needs_review: number;
  recent_events: number;
}

export default function Notifications() {
  const navigate = useNavigate();
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [summary, setSummary] = useState<NotificationSummary>({
    unread: 0,
    critical: 0,
    needs_review: 0,
    recent_events: 0,
  });
  const [loading, setLoading] = useState(true);
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [isMarkingAll, setIsMarkingAll] = useState(false);

  const fetchNotifications = async () => {
    setLoading(true);
    try {
      const res = await api.get(`/api/v1/notifications/?category=${categoryFilter}&limit=100`);
      setNotifications(res.data.data || []);
      if (res.data.summary) {
        setSummary(res.data.summary);
      }
    } catch (err) {
      console.error('Failed to load notifications:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchNotifications();
  }, [categoryFilter]);

  const handleMarkAsRead = async (id: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    try {
      await api.post(`/api/v1/notifications/${id}/read`);
      setNotifications(prev =>
        prev.map(n => (n.id === id ? { ...n, is_read: true, read_at: new Date().toISOString() } : n))
      );
      setSummary(prev => ({
        ...prev,
        unread: Math.max(0, prev.unread - 1),
      }));
    } catch (err) {
      console.error('Failed to mark notification as read:', err);
    }
  };

  const handleMarkAllRead = async () => {
    setIsMarkingAll(true);
    try {
      await api.post('/api/v1/notifications/read-all');
      setNotifications(prev =>
        prev.map(n => ({ ...n, is_read: true, read_at: new Date().toISOString() }))
      );
      setSummary(prev => ({
        ...prev,
        unread: 0,
        critical: 0,
        needs_review: 0,
      }));
    } catch (err) {
      console.error('Failed to mark all as read:', err);
    } finally {
      setIsMarkingAll(false);
    }
  };

  const handleNotificationClick = (item: NotificationItem) => {
    if (!item.is_read) {
      handleMarkAsRead(item.id);
    }
    if (item.action_url) {
      navigate(item.action_url);
    }
  };

  const getSeverityBadge = (severity: string) => {
    switch (severity) {
      case 'critical':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-100 text-red-800 border border-red-200">
            <ShieldAlert size={12} /> Critical
          </span>
        );
      case 'warning':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-200">
            <AlertTriangle size={12} /> Action Required
          </span>
        );
      case 'success':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-200">
            <CheckCircle size={12} /> Resolved
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-800 border border-blue-200">
            <Info size={12} /> Info
          </span>
        );
    }
  };

  const getCategoryIcon = (category: string, severity: string) => {
    if (severity === 'critical') return <ShieldAlert className="text-red-500" size={20} />;
    if (severity === 'warning') return <AlertTriangle className="text-amber-500" size={20} />;
    if (category === 'pipeline') return <Bot className="text-purple-500" size={20} />;
    if (category === 'reports') return <FileText className="text-indigo-500" size={20} />;
    return <Sparkles className="text-blue-500" size={20} />;
  };

  const categories = [
    { id: 'all', label: 'All Events' },
    { id: 'unread', label: 'Unread' },
    { id: 'verification', label: 'Verification' },
    { id: 'attribution', label: 'Attribution' },
    { id: 'identity', label: 'Identity' },
    { id: 'integrity', label: 'Integrity' },
    { id: 'metrics', label: 'Metrics' },
    { id: 'pipeline', label: 'Pipeline' },
    { id: 'reports', label: 'Reports' },
  ];

  const filteredNotifications = notifications.filter(n => {
    if (!searchQuery.trim()) return true;
    const query = searchQuery.toLowerCase();
    return (
      n.title.toLowerCase().includes(query) ||
      n.message.toLowerCase().includes(query) ||
      (n.source_agent && n.source_agent.toLowerCase().includes(query))
    );
  });

  return (
    <div className="space-y-6 max-w-6xl mx-auto pb-12">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white/90 backdrop-blur-md p-6 rounded-2xl border border-gray-200/80 shadow-sm">
        <div>
          <div className="flex items-center gap-2">
            <div className="p-2 bg-blue-50 text-blue-700 rounded-lg border border-blue-100">
              <Bell size={24} />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Notifications</h1>
              <p className="text-sm text-gray-500 mt-0.5">
                Research monitoring events and actions requiring attention.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchNotifications}
            disabled={loading}
            className="flex items-center gap-1.5 px-3.5 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-xl hover:bg-gray-50 hover:text-gray-900 transition-colors shadow-sm disabled:opacity-50"
            title="Refresh notifications"
          >
            <RotateCw size={16} className={loading ? 'animate-spin' : ''} />
            <span>Refresh</span>
          </button>

          {summary.unread > 0 && (
            <button
              onClick={handleMarkAllRead}
              disabled={isMarkingAll}
              className="flex items-center gap-1.5 px-4 py-2 text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-xl shadow-sm transition-colors disabled:opacity-50"
            >
              <CheckCheck size={16} />
              <span>Mark All Read</span>
            </button>
          )}
        </div>
      </div>

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white/90 backdrop-blur-md p-5 rounded-2xl border border-gray-200/80 shadow-sm flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-blue-50 border border-blue-100 flex items-center justify-center text-blue-600 font-bold">
            <Bell size={22} />
          </div>
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Unread</p>
            <p className="text-2xl font-extrabold text-gray-900 mt-0.5">{summary.unread}</p>
          </div>
        </div>

        <div className="bg-white/90 backdrop-blur-md p-5 rounded-2xl border border-gray-200/80 shadow-sm flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-red-50 border border-red-100 flex items-center justify-center text-red-600 font-bold">
            <ShieldAlert size={22} />
          </div>
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Critical</p>
            <p className="text-2xl font-extrabold text-gray-900 mt-0.5">{summary.critical}</p>
          </div>
        </div>

        <div className="bg-white/90 backdrop-blur-md p-5 rounded-2xl border border-gray-200/80 shadow-sm flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-amber-50 border border-amber-100 flex items-center justify-center text-amber-600 font-bold">
            <AlertTriangle size={22} />
          </div>
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Needs Review</p>
            <p className="text-2xl font-extrabold text-gray-900 mt-0.5">{summary.needs_review}</p>
          </div>
        </div>

        <div className="bg-white/90 backdrop-blur-md p-5 rounded-2xl border border-gray-200/80 shadow-sm flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-purple-50 border border-purple-100 flex items-center justify-center text-purple-600 font-bold">
            <Bot size={22} />
          </div>
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Recent Events</p>
            <p className="text-2xl font-extrabold text-gray-900 mt-0.5">{summary.recent_events}</p>
          </div>
        </div>
      </div>

      {/* Filter Tabs & Search */}
      <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center justify-between">
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0 custom-scrollbar">
          {categories.map(cat => (
            <button
              key={cat.id}
              onClick={() => setCategoryFilter(cat.id)}
              className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-all ${
                categoryFilter === cat.id
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'bg-white/80 text-gray-600 hover:bg-white hover:text-gray-900 border border-gray-200'
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>

        <div className="relative w-full sm:w-64">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={16} />
          <input
            type="text"
            placeholder="Search events..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 text-xs bg-white border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-100 focus:border-blue-400"
          />
        </div>
      </div>

      {/* Notifications List */}
      <div className="space-y-3">
        {loading ? (
          <div className="bg-white/90 backdrop-blur-md p-12 rounded-2xl border border-gray-200/80 text-center text-gray-500">
            <RotateCw className="animate-spin mx-auto mb-2 text-blue-600" size={28} />
            <p className="text-sm font-medium">Loading research events...</p>
          </div>
        ) : filteredNotifications.length === 0 ? (
          <div className="bg-white/90 backdrop-blur-md p-12 rounded-2xl border border-gray-200/80 text-center">
            <div className="w-16 h-16 bg-blue-50 rounded-full flex items-center justify-center mx-auto mb-3 text-blue-600">
              <Bell size={28} />
            </div>
            <h3 className="text-lg font-bold text-gray-900">No new research monitoring events.</h3>
            <p className="text-sm text-gray-500 mt-1 max-w-md mx-auto">
              All research activities, verification queues, and pipeline processes are currently up to date.
            </p>
          </div>
        ) : (
          filteredNotifications.map(n => (
            <div
              key={n.id}
              onClick={() => handleNotificationClick(n)}
              className={`p-5 rounded-2xl border transition-all cursor-pointer ${
                !n.is_read
                  ? 'bg-white border-blue-200/80 shadow-md ring-1 ring-blue-50'
                  : 'bg-white/70 border-gray-200/80 hover:bg-white/90 opacity-90'
              }`}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-start gap-3.5">
                  <div className="p-2.5 rounded-xl bg-gray-50 border border-gray-100 mt-0.5">
                    {getCategoryIcon(n.category, n.severity)}
                  </div>
                  <div>
                    <div className="flex flex-wrap items-center gap-2 mb-1">
                      <h4 className="font-bold text-gray-900 text-base">{n.title}</h4>
                      {getSeverityBadge(n.severity)}
                      {!n.is_read && (
                        <span className="w-2 h-2 rounded-full bg-blue-600" title="Unread"></span>
                      )}
                    </div>
                    <p className="text-sm text-gray-600 leading-relaxed">{n.message}</p>
                    
                    <div className="flex flex-wrap items-center gap-4 mt-3 text-xs text-gray-400 font-medium">
                      {n.source_agent && (
                        <span className="inline-flex items-center gap-1 text-gray-600 bg-gray-100 px-2 py-0.5 rounded-md">
                          <Bot size={12} /> {n.source_agent}
                        </span>
                      )}
                      <span>
                        {n.created_at ? new Date(n.created_at).toLocaleString() : 'Just now'}
                      </span>
                      {n.action_url && (
                        <span className="inline-flex items-center gap-1 text-blue-600 hover:underline">
                          <ExternalLink size={12} /> View Related Record
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  {!n.is_read && (
                    <button
                      onClick={(e) => handleMarkAsRead(n.id, e)}
                      className="px-3 py-1.5 text-xs font-semibold text-gray-600 hover:text-blue-700 bg-gray-50 hover:bg-blue-50 rounded-lg border border-gray-200 transition-colors"
                      title="Mark as read"
                    >
                      Mark Read
                    </button>
                  )}
                  {n.action_url && (
                    <button
                      onClick={() => navigate(n.action_url!)}
                      className="p-1.5 text-gray-400 hover:text-blue-600 transition-colors"
                      title="Navigate to resource"
                    >
                      <ExternalLink size={16} />
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
