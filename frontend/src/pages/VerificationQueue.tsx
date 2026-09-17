import React, { useEffect, useState } from 'react';
import api from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import {
  CheckSquare,
  XCircle,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Search,
  Filter,
  ExternalLink,
  ShieldAlert,
  UserCheck,
  FileText,
  History,
  Send,
  Sparkles,
  BookOpen,
  Building,
  RefreshCw,
} from 'lucide-react';

interface AuthorInfo {
  name: string;
  position?: number;
  confidence?: number;
  is_corresponding?: boolean;
  faculty?: {
    id: string;
    name: string;
    department?: string;
    designation?: string;
    email?: string;
  };
}

interface PublicationSourceInfo {
  source_system: string;
  source_id?: string;
  source_url?: string;
  discovered_at?: string;
}

interface PublicationDetails {
  id: string;
  title: string;
  doi?: string;
  source_url?: string;
  year?: number;
  journal_name?: string;
  conference_name?: string;
  publisher?: string;
  publication_type?: string;
  citation_count?: number;
  risk_level?: string;
  risk_reasons?: any;
  verification_status?: string;
  metadata_confidence?: number;
  attribution_confidence?: number;
  authors?: AuthorInfo[];
  sources?: PublicationSourceInfo[];
}

const getPublicationUrl = (pub?: PublicationDetails, taskEvidence?: any): string | null => {
  if (!pub) return null;
  // 1. Existing verified source_url if available
  if (pub.source_url && typeof pub.source_url === 'string' && pub.source_url.startsWith('http')) {
    return pub.source_url;
  }
  if (pub.sources && Array.isArray(pub.sources)) {
    const srcWithUrl = pub.sources.find((s: any) => s?.source_url && String(s.source_url).startsWith('http'));
    if (srcWithUrl?.source_url) return srcWithUrl.source_url;
  }
  if (taskEvidence?.source_url && typeof taskEvidence.source_url === 'string' && taskEvidence.source_url.startsWith('http')) {
    return taskEvidence.source_url;
  }
  // 2. Otherwise, if the publication has a DOI, open: https://doi.org/<exact DOI>
  const rawDoi = pub.doi || taskEvidence?.doi;
  if (rawDoi && typeof rawDoi === 'string' && rawDoi.trim()) {
    const cleanDoi = rawDoi.trim();
    if (cleanDoi.startsWith('http://') || cleanDoi.startsWith('https://')) {
      return cleanDoi;
    }
    const strippedDoi = cleanDoi.replace(/^doi:\s*/i, '').replace(/^https?:\/\/doi\.org\//i, '');
    return `https://doi.org/${strippedDoi}`;
  }
  // 3. If neither source_url nor DOI exists, leave the title without a link
  return null;
};

interface ReviewTaskItem {
  id: string;
  task_type: string;
  priority: string;
  status: string;
  entity_type: string;
  entity_id: string;
  explanation: string;
  evidence: {
    evidence_chain?: string[];
    score?: number;
    [key: string]: any;
  };
  options?: any;
  decision?: string;
  decision_detail?: any;
  decided_by?: string;
  decided_at?: string;
  agent_name?: string;
  created_at: string;
  publication?: PublicationDetails;
  faculty?: {
    id: string;
    name: string;
    department?: string;
    designation?: string;
    email?: string;
    employee_id?: string;
  };
  review_actions_allowed: boolean;
}

interface HistoryItem {
  id: string;
  task_type: string;
  entity_type: string;
  entity_id?: string;
  entity_title?: string;
  priority: string;
  decision: string;
  decision_detail: {
    comment?: string;
    previous_entity_status?: string;
    new_entity_status?: string;
    reviewer_name?: string;
    reviewer_email?: string;
    [key: string]: any;
  };
  reviewer_name: string;
  reviewer_email: string;
  decided_at?: string;
  explanation?: string;
}

interface QueueStats {
  pending: number;
  high_priority: number;
  resolved: number;
  approved: number;
  rejected: number;
  corrections: number;
  user_role: string;
}

export default function VerificationQueue() {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<'pending' | 'history'>('pending');
  const [tasks, setTasks] = useState<ReviewTaskItem[]>([]);
  const [historyItems, setHistoryItems] = useState<HistoryItem[]>([]);
  const [stats, setStats] = useState<QueueStats>({
    pending: 0,
    high_priority: 0,
    resolved: 0,
    approved: 0,
    rejected: 0,
    corrections: 0,
    user_role: 'faculty',
  });
  const [loading, setLoading] = useState(true);
  const [errorState, setErrorState] = useState<'auth' | 'forbidden' | 'error' | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [notification, setNotification] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [priorityFilter, setPriorityFilter] = useState<string>('all');
  const [typeFilter, setTypeFilter] = useState<string>('all');

  // Decision Modal State
  const [selectedTask, setSelectedTask] = useState<ReviewTaskItem | null>(null);
  const [decisionType, setDecisionType] = useState<'approve' | 'reject' | 'request_correction' | null>(null);
  const [reviewComment, setReviewComment] = useState('');

  const isAdmin = user?.role === 'research_admin' || user?.role === 'super_admin' || user?.role === 'dept_admin';

  // Load Queue & Stats
  const loadQueue = async () => {
    setLoading(true);
    setErrorState(null);
    try {
      const [statsRes, queueRes] = await Promise.all([
        api.get('/api/v1/review/stats'),
        api.get('/api/v1/review/queue', {
          params: {
            status: 'pending',
            priority: priorityFilter !== 'all' ? priorityFilter : undefined,
            task_type: typeFilter !== 'all' ? typeFilter : undefined,
            search: searchQuery.trim() || undefined,
          },
        }),
      ]);
      setStats(statsRes.data);
      const queueData = Array.isArray(queueRes.data) ? queueRes.data : queueRes.data?.data || [];
      setTasks(queueData);
      setErrorState(null);
    } catch (err: any) {
      console.error('Failed to load review queue', err);
      if (err.response?.status === 401) {
        setErrorState('auth');
      } else if (err.response?.status === 403) {
        setErrorState('forbidden');
      } else {
        setErrorState('error');
      }
      setTasks([]);
    } finally {
      setLoading(false);
    }
  };

  // Load Audit History
  const loadHistory = async () => {
    setHistoryLoading(true);
    try {
      const res = await api.get('/api/v1/review/history');
      const data = Array.isArray(res.data) ? res.data : res.data?.data || [];
      setHistoryItems(data);
    } catch (err) {
      console.error('Failed to load review history', err);
      setHistoryItems([]);
    } finally {
      setHistoryLoading(false);
    }
  };

  useEffect(() => {
    loadQueue();
  }, [priorityFilter, typeFilter]);

  useEffect(() => {
    if (activeTab === 'history') {
      loadHistory();
    }
  }, [activeTab]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    loadQueue();
  };

  const openDecisionModal = (task: ReviewTaskItem, type: 'approve' | 'reject' | 'request_correction') => {
    setSelectedTask(task);
    setDecisionType(type);
    setReviewComment('');
  };

  const closeDecisionModal = () => {
    setSelectedTask(null);
    setDecisionType(null);
    setReviewComment('');
  };

  const submitDecision = async () => {
    if (!selectedTask || !decisionType) return;
    setActionLoading(true);
    try {
      await api.post(`/api/v1/review/${selectedTask.id}/decide`, {
        decision: decisionType,
        comment: reviewComment.trim() || undefined,
      });

      setNotification({
        type: 'success',
        message: `Task successfully resolved with decision: ${decisionType.toUpperCase().replace('_', ' ')}!`,
      });

      closeDecisionModal();
      loadQueue();
      if (activeTab === 'history') {
        loadHistory();
      }
    } catch (err: any) {
      console.error('Decision submission failed', err);
      setNotification({
        type: 'error',
        message: err.response?.data?.detail || 'Failed to submit review decision. Please try again.',
      });
    } finally {
      setActionLoading(false);
      setTimeout(() => setNotification(null), 5000);
    }
  };

  const getPriorityBadgeClass = (priority: string) => {
    switch (priority?.toLowerCase()) {
      case 'critical':
        return 'bg-red-100 text-red-800 border-red-300 font-bold';
      case 'high':
        return 'bg-amber-100 text-amber-800 border-amber-300 font-semibold';
      case 'medium':
        return 'bg-blue-100 text-blue-800 border-blue-200';
      default:
        return 'bg-gray-100 text-gray-700 border-gray-200';
    }
  };

  const getStatusBadgeClass = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'verified':
      case 'human_verified':
      case 'approve':
        return 'bg-emerald-100 text-emerald-800 border-emerald-300';
      case 'partially_verified':
        return 'bg-sky-100 text-sky-800 border-sky-300';
      case 'needs_review':
      case 'pending':
        return 'bg-amber-100 text-amber-800 border-amber-300';
      case 'rejected':
      case 'human_rejected':
      case 'reject':
        return 'bg-rose-100 text-rose-800 border-rose-300';
      case 'human_corrected':
      case 'request_correction':
        return 'bg-purple-100 text-purple-800 border-purple-300';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  return (
    <div className="space-y-6 pb-12">
      {/* Toast Notification */}
      {notification && (
        <div
          className={`p-4 rounded-xl border flex items-center justify-between shadow-sm animate-in fade-in duration-200 ${
            notification.type === 'success'
              ? 'bg-emerald-50 text-emerald-900 border-emerald-200'
              : 'bg-rose-50 text-rose-900 border-rose-200'
          }`}
        >
          <div className="flex items-center gap-3">
            {notification.type === 'success' ? (
              <CheckCircle2 className="text-emerald-600 shrink-0" size={20} />
            ) : (
              <AlertTriangle className="text-rose-600 shrink-0" size={20} />
            )}
            <span className="font-medium text-sm">{notification.message}</span>
          </div>
          <button
            onClick={() => setNotification(null)}
            className="text-gray-400 hover:text-gray-700 text-sm font-semibold ml-4"
          >
            ✕
          </button>
        </div>
      )}

      {/* Page Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-white p-6 rounded-2xl border border-gray-200/80 shadow-sm">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2.5 py-0.5 rounded-full text-xs font-bold uppercase tracking-wider bg-blue-100 text-blue-800">
              Human Review & Verification
            </span>
            <span className="text-xs text-gray-500 font-medium">Quality Assurance & Attribution Review</span>
          </div>
          <h1 className="text-2xl font-extrabold text-gray-900 mt-2 flex items-center gap-2">
            <CheckSquare className="text-blue-600" size={28} />
            Verification Queue & Human Review
          </h1>
          <p className="text-sm text-gray-600 mt-1">
            {isAdmin
              ? 'Manage verification flags, audit unresolved evidence contradictions, and confirm publication attributions.'
              : 'These publications have verified bibliographic metadata but require faculty confirmation of authorship.'}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => {
              if (activeTab === 'pending') loadQueue();
              else loadHistory();
            }}
            className="px-4 py-2 bg-gray-50 hover:bg-gray-100 text-gray-700 border border-gray-300 rounded-xl text-sm font-medium flex items-center gap-2 transition-colors shadow-sm"
          >
            <RefreshCw size={15} className={loading || historyLoading ? 'animate-spin' : ''} /> Refresh
          </button>
        </div>
      </div>

      {/* Information Banner on Metadata vs Attribution */}
      {!isAdmin && (
        <div className="p-4 rounded-xl bg-blue-50/80 border border-blue-200/80 text-xs text-blue-900 flex items-start gap-2.5 shadow-xs">
          <Sparkles className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
          <div className="leading-relaxed">
            <span className="font-bold">METADATA VERIFIED ≠ FACULTY ATTRIBUTION VERIFIED:</span> The bibliographic metadata (title, DOI, citations, publication venue) for these publications has already been verified by institutional data pipelines. Your confirmation is required specifically to verify faculty authorship and self-attribution.
          </div>
        </div>
      )}

      {/* Stats Summary Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="stat-card p-5 bg-white border border-gray-200 rounded-2xl shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
              {isAdmin ? 'Pending Review' : 'Faculty Attribution Review'}
            </p>
            <h3 className="text-2xl font-black text-gray-900 mt-1">{stats.pending}</h3>
            <p className="text-xs text-amber-600 font-medium mt-0.5 flex items-center gap-1">
              <Clock size={12} /> {isAdmin ? 'Awaiting audit' : 'Attribution reviews pending'}
            </p>
          </div>
          <div className="p-3 bg-amber-50 rounded-2xl text-amber-600 border border-amber-100">
            <Clock size={24} />
          </div>
        </div>

        <div className="stat-card p-5 bg-white border border-gray-200 rounded-2xl shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">High Priority Flags</p>
            <h3 className="text-2xl font-black text-gray-900 mt-1">{stats.high_priority}</h3>
            <p className="text-xs text-red-600 font-medium mt-0.5 flex items-center gap-1">
              <ShieldAlert size={12} /> Requires attention
            </p>
          </div>
          <div className="p-3 bg-red-50 rounded-2xl text-red-600 border border-red-100">
            <ShieldAlert size={24} />
          </div>
        </div>

        <div className="stat-card p-5 bg-white border border-gray-200 rounded-2xl shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Approved & Verified</p>
            <h3 className="text-2xl font-black text-gray-900 mt-1">{stats.approved}</h3>
            <p className="text-xs text-emerald-600 font-medium mt-0.5 flex items-center gap-1">
              <CheckCircle2 size={12} /> Provenance confirmed
            </p>
          </div>
          <div className="p-3 bg-emerald-50 rounded-2xl text-emerald-600 border border-emerald-100">
            <CheckCircle2 size={24} />
          </div>
        </div>

        <div className="stat-card p-5 bg-white border border-gray-200 rounded-2xl shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Total Resolved</p>
            <h3 className="text-2xl font-black text-gray-900 mt-1">{stats.resolved}</h3>
            <p className="text-xs text-blue-600 font-medium mt-0.5 flex items-center gap-1">
              <History size={12} /> Audit trail logged
            </p>
          </div>
          <div className="p-3 bg-blue-50 rounded-2xl text-blue-600 border border-blue-100">
            <History size={24} />
          </div>
        </div>
      </div>

      {/* Tabs Navigation */}
      <div className="flex border-b border-gray-200 bg-white px-4 pt-3 rounded-2xl shadow-sm">
        <button
          onClick={() => setActiveTab('pending')}
          className={`pb-3 px-4 font-semibold text-sm flex items-center gap-2 border-b-2 transition-colors ${
            activeTab === 'pending'
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-gray-500 hover:text-gray-900'
          }`}
        >
          <Clock size={16} /> {isAdmin ? 'Pending Queue' : 'Faculty Attribution Queue'}
          <span className="px-2 py-0.5 text-xs rounded-full bg-blue-100 text-blue-800 font-bold">
            {stats.pending}
          </span>
        </button>

        <button
          onClick={() => setActiveTab('history')}
          className={`pb-3 px-4 font-semibold text-sm flex items-center gap-2 border-b-2 transition-colors ${
            activeTab === 'history'
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-gray-500 hover:text-gray-900'
          }`}
        >
          <History size={16} /> Decision History & Audit Trail
          <span className="px-2 py-0.5 text-xs rounded-full bg-gray-100 text-gray-700 font-bold">
            {stats.resolved}
          </span>
        </button>
      </div>

      {/* TAB 1: PENDING QUEUE */}
      {activeTab === 'pending' && (
        <div className="space-y-4">
          {/* Filter Bar */}
          <div className="bg-white p-4 rounded-2xl border border-gray-200/80 shadow-sm flex flex-col md:flex-row gap-3 items-stretch md:items-center justify-between">
            <form onSubmit={handleSearchSubmit} className="flex-1 relative">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search publications, faculty authors, or review reasons..."
                className="w-full pl-10 pr-4 py-2 text-sm bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 text-gray-900 placeholder:text-gray-400"
              />
            </form>

            <div className="flex flex-wrap items-center gap-3">
              <div className="flex items-center gap-2">
                <Filter size={15} className="text-gray-400" />
                <span className="text-xs font-semibold text-gray-500 uppercase">Priority:</span>
                <select
                  value={priorityFilter}
                  onChange={(e) => setPriorityFilter(e.target.value)}
                  className="bg-gray-50 border border-gray-200 text-gray-700 text-xs font-medium rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                >
                  <option value="all">All Priorities</option>
                  <option value="critical">Critical</option>
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>
              </div>

              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-gray-500 uppercase">Task:</span>
                <select
                  value={typeFilter}
                  onChange={(e) => setTypeFilter(e.target.value)}
                  className="bg-gray-50 border border-gray-200 text-gray-700 text-xs font-medium rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                >
                  <option value="all">All Task Types</option>
                  <option value="verification_review">Verification Review</option>
                  <option value="attribution_ambiguous">Attribution Ambiguous</option>
                  <option value="IDENTIFIER_MATCH">Identifier Match</option>
                </select>
              </div>
            </div>
          </div>

          {/* Review Tasks List / UI States */}
          {loading ? (
            <div className="bg-white p-12 rounded-2xl border border-gray-200 text-center space-y-3 shadow-sm">
              <RefreshCw className="animate-spin text-blue-600 mx-auto" size={32} />
              <p className="text-sm font-semibold text-gray-700">Loading verification queue...</p>
              <p className="text-xs text-gray-400">Fetching pending review tasks and assessed evidence.</p>
            </div>
          ) : errorState === 'auth' ? (
            <div className="bg-white p-12 rounded-2xl border border-amber-200 text-center space-y-4 shadow-sm">
              <div className="w-16 h-16 bg-amber-50 text-amber-600 rounded-full flex items-center justify-center mx-auto border border-amber-200">
                <AlertTriangle size={32} />
              </div>
              <div className="space-y-1">
                <h3 className="text-lg font-bold text-gray-900">Your session has expired</h3>
                <p className="text-sm text-gray-500 max-w-md mx-auto">
                  Please log in again to access the verification queue and review your publication attributions.
                </p>
              </div>
              <button
                onClick={() => { window.location.href = '/login'; }}
                className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs rounded-xl shadow-sm transition-colors inline-flex items-center gap-2"
              >
                <UserCheck size={15} /> Sign In Again
              </button>
            </div>
          ) : errorState === 'forbidden' ? (
            <div className="bg-white p-12 rounded-2xl border border-red-200 text-center space-y-4 shadow-sm">
              <div className="w-16 h-16 bg-red-50 text-red-600 rounded-full flex items-center justify-center mx-auto border border-red-200">
                <ShieldAlert size={32} />
              </div>
              <div className="space-y-1">
                <h3 className="text-lg font-bold text-gray-900">Access Restricted</h3>
                <p className="text-sm text-gray-500 max-w-md mx-auto">
                  You are not authorized to view this verification queue.
                </p>
              </div>
            </div>
          ) : errorState === 'error' ? (
            <div className="bg-white p-12 rounded-2xl border border-gray-200 text-center space-y-4 shadow-sm">
              <div className="w-16 h-16 bg-rose-50 text-rose-600 rounded-full flex items-center justify-center mx-auto border border-rose-200">
                <AlertTriangle size={32} />
              </div>
              <div className="space-y-1">
                <h3 className="text-lg font-bold text-gray-900">Unable to load verification queue</h3>
                <p className="text-sm text-gray-500 max-w-md mx-auto">
                  A network or server error occurred while retrieving verification tasks. Please try again.
                </p>
              </div>
              <button
                onClick={loadQueue}
                className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs rounded-xl shadow-sm transition-colors inline-flex items-center gap-2"
              >
                <RefreshCw size={15} /> Retry
              </button>
            </div>
          ) : tasks.length === 0 ? (
            <div className="bg-white p-12 rounded-2xl border border-gray-200 text-center space-y-4 shadow-sm">
              <div className="w-16 h-16 bg-emerald-50 text-emerald-600 rounded-full flex items-center justify-center mx-auto border border-emerald-100">
                <CheckCircle2 size={32} />
              </div>
              <div>
                <h3 className="text-lg font-bold text-gray-900">Queue is Clear</h3>
                <p className="text-sm text-gray-500 max-w-md mx-auto mt-1">
                  There are no pending review tasks matching your current filter criteria. All verification assessments are up to date.
                </p>
              </div>
            </div>
          ) : (
            <div className="grid gap-4">
              {tasks.map((task) => {
                const pub = task.publication;
                const facultyAuthors = pub?.authors?.filter((a) => a.faculty) || [];
                const confidenceScore = task.evidence?.score ?? pub?.metadata_confidence ?? 0;
                const evidenceChain = task.evidence?.evidence_chain || [];
                const isAttributionTask = task.task_type === 'attribution_ambiguous';
                const canAct = task.review_actions_allowed || isAdmin;

                return (
                  <div
                    key={task.id}
                    className="bg-white border border-gray-200/90 hover:border-blue-300 rounded-2xl p-6 shadow-sm transition-all duration-200 space-y-5"
                  >
                    {/* Top Bar / Meta */}
                    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-gray-100 pb-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={`px-2.5 py-1 rounded-lg text-xs border ${getPriorityBadgeClass(task.priority)}`}>
                          {task.priority.toUpperCase()} PRIORITY
                        </span>
                        <span className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-gray-100 text-gray-700 border border-gray-200">
                          {task.task_type.replace('_', ' ').toUpperCase()}
                        </span>
                        {pub?.verification_status && (
                          <span className={`px-2.5 py-1 rounded-lg text-xs font-semibold border ${getStatusBadgeClass(pub.verification_status)}`}>
                            METADATA: {pub.verification_status.replace('_', ' ').toUpperCase()}
                          </span>
                        )}
                        {isAttributionTask && (
                          <span className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-300 flex items-center gap-1">
                            <AlertTriangle size={12} /> ATTRIBUTION: HUMAN REVIEW REQUIRED
                          </span>
                        )}
                        {pub?.risk_level && pub.risk_level !== 'none' && (
                          <span className="px-2 py-0.5 rounded-lg text-xs font-semibold bg-red-50 text-red-700 border border-red-200 flex items-center gap-1">
                            <ShieldAlert size={12} /> Risk: {pub.risk_level.toUpperCase()}
                          </span>
                        )}
                      </div>

                      <span className="text-xs text-gray-400 font-medium">
                        Created {new Date(task.created_at).toLocaleDateString(undefined, { dateStyle: 'medium' })}
                      </span>
                    </div>

                    {/* Main Content Area */}
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                      {/* Left 2 Cols: Publication & Authors Details */}
                      <div className="lg:col-span-2 space-y-3">
                        {pub ? (
                          <>
                            {(() => {
                              const pubUrl = getPublicationUrl(pub, task.evidence);
                              return pubUrl ? (
                                <a
                                  href={pubUrl}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-lg font-bold text-blue-600 hover:text-blue-800 hover:underline leading-snug inline-flex items-center gap-1.5 group"
                                  title="Open publication in new tab"
                                >
                                  <span>{pub.title}</span>
                                  <ExternalLink size={15} className="shrink-0 text-blue-500 group-hover:text-blue-700 transition-transform group-hover:translate-x-0.5" />
                                </a>
                              ) : (
                                <h3 className="text-lg font-bold text-blue-600 leading-snug">
                                  {pub.title}
                                </h3>
                              );
                            })()}

                            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-600">
                              {pub.year && (
                                <span className="flex items-center gap-1 font-medium">
                                  <BookOpen size={13} className="text-gray-400" /> Year: <strong>{pub.year}</strong>
                                </span>
                              )}
                              {(pub.journal_name || pub.conference_name) && (
                                <span className="font-medium text-gray-700">
                                  Venue: <em>{pub.journal_name || pub.conference_name}</em>
                                </span>
                              )}
                              {pub.publication_type && (
                                <span className="bg-gray-100 px-2 py-0.5 rounded text-gray-600 font-medium">
                                  {pub.publication_type}
                                </span>
                              )}
                            </div>

                            {/* DOI & External Links */}
                            {pub.doi && (
                              <div className="flex items-center gap-2 text-xs text-blue-600">
                                <span className="font-semibold text-gray-500">DOI:</span>
                                <a
                                  href={`https://doi.org/${pub.doi.replace(/^https?:\/\/doi\.org\//, '')}`}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="hover:underline font-mono inline-flex items-center gap-1 font-medium text-blue-600 bg-blue-50 px-2 py-0.5 rounded border border-blue-200"
                                >
                                  {pub.doi} <ExternalLink size={11} />
                                </a>
                              </div>
                            )}

                            {/* Faculty Authors */}
                            <div className="pt-2">
                              <p className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-1.5 flex items-center gap-1">
                                <UserCheck size={13} className="text-blue-600" /> Linked Faculty Profile(s):
                              </p>
                              <div className="flex flex-wrap gap-2">
                                {facultyAuthors.length > 0 ? (
                                  facultyAuthors.map((auth, idx) => (
                                    <div
                                      key={idx}
                                      className="bg-blue-50/70 border border-blue-200/80 rounded-xl px-3 py-1.5 text-xs text-gray-800 flex items-center gap-2"
                                    >
                                      <Building size={12} className="text-blue-600" />
                                      <div>
                                        <span className="font-bold text-gray-900">{auth.faculty?.name}</span>
                                        {auth.faculty?.department && (
                                          <span className="text-gray-500 ml-1">({auth.faculty.department})</span>
                                        )}
                                      </div>
                                    </div>
                                  ))
                                ) : (
                                  <div className="text-xs text-gray-500 italic bg-gray-50 px-3 py-1.5 rounded-lg border border-gray-200">
                                    Author raw text: {pub.authors?.map((a) => a.name).join(', ') || 'None parsed'}
                                  </div>
                                )}
                              </div>
                            </div>
                          </>
                        ) : task.faculty ? (
                          <div className="space-y-2">
                            <h3 className="text-lg font-bold text-gray-900">
                              Faculty Verification: {task.faculty.name}
                            </h3>
                            <p className="text-sm text-gray-600">
                              {task.faculty.designation} • {task.faculty.department} ({task.faculty.email})
                            </p>
                          </div>
                        ) : (
                          <p className="text-sm text-gray-800 font-semibold">{task.explanation}</p>
                        )}

                        {/* Explanation Note */}
                        <div className="bg-amber-50/70 border border-amber-200 rounded-xl p-3 text-xs text-amber-900 flex items-start gap-2 mt-2">
                          <AlertTriangle className="text-amber-600 shrink-0 mt-0.5" size={15} />
                          <div>
                            <span className="font-bold">Reason for Review: </span>
                            {task.explanation}
                          </div>
                        </div>
                      </div>

                      {/* Right Col: Evidence Chain & Confidence */}
                      <div className="bg-gray-50/80 rounded-xl p-4 border border-gray-200/80 space-y-4 flex flex-col justify-between">
                        <div className="space-y-3">
                          <div className="flex justify-between items-center">
                            <span className="text-xs font-bold text-gray-500 uppercase tracking-wider">
                              Assessed Confidence
                            </span>
                            <span className="text-xs font-extrabold text-gray-900">{confidenceScore.toFixed(0)}%</span>
                          </div>

                          {/* Progress Bar */}
                          <div className="w-full bg-gray-200 h-2 rounded-full overflow-hidden">
                            <div
                              className={`h-full rounded-full transition-all duration-300 ${
                                confidenceScore >= 80
                                  ? 'bg-emerald-500'
                                  : confidenceScore >= 50
                                  ? 'bg-amber-500'
                                  : 'bg-rose-500'
                              }`}
                              style={{ width: `${Math.min(100, Math.max(5, confidenceScore))}%` }}
                            />
                          </div>

                          {/* Evidence Chain Items */}
                          <div>
                            <p className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-1.5 flex items-center gap-1">
                              <Sparkles size={12} className="text-amber-500" /> Evidence Chain Signals:
                            </p>
                            {evidenceChain.length > 0 ? (
                              <ul className="space-y-1 text-xs text-gray-600">
                                {evidenceChain.map((ev, idx) => (
                                  <li key={idx} className="flex items-start gap-1.5">
                                    <span className="text-blue-500 font-bold">•</span>
                                    <span>{ev}</span>
                                  </li>
                                ))}
                              </ul>
                            ) : (
                              <p className="text-xs text-gray-400 italic">No automated contradiction breakdown.</p>
                            )}
                          </div>

                          {/* Discovered Sources */}
                          {pub?.sources && pub.sources.length > 0 && (
                            <div className="pt-1">
                              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">
                                Data Sources:
                              </p>
                              <div className="flex flex-wrap gap-1.5">
                                {pub.sources.map((s, idx) => (
                                  <span
                                    key={idx}
                                    className="px-2 py-0.5 bg-white border border-gray-200 text-gray-700 rounded text-[11px] font-medium uppercase"
                                  >
                                    {s.source_system}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>

                        {/* Actions Panel */}
                        {canAct ? (
                          isAttributionTask && !isAdmin ? (
                            <div className="pt-3 border-t border-gray-200 flex flex-col gap-2">
                              <button
                                onClick={() => openDecisionModal(task, 'approve')}
                                className="w-full py-2.5 px-3 bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs rounded-xl flex items-center justify-center gap-1.5 shadow-sm transition-colors"
                              >
                                <CheckCircle2 size={15} /> ✓ THIS IS MY PUBLICATION
                              </button>
                              <div className="grid grid-cols-2 gap-2">
                                <button
                                  onClick={() => openDecisionModal(task, 'reject')}
                                  className="py-2 px-2.5 bg-rose-50 hover:bg-rose-100 text-rose-800 border border-rose-300 font-bold text-xs rounded-xl flex items-center justify-center gap-1 transition-colors"
                                  title="Reject attribution to your profile"
                                >
                                  <XCircle size={13} /> ✕ NOT MINE
                                </button>
                                <button
                                  onClick={() => openDecisionModal(task, 'request_correction')}
                                  className="py-2 px-2.5 bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-300 font-bold text-xs rounded-xl flex items-center justify-center gap-1 transition-colors"
                                  title="Request metadata correction"
                                >
                                  <AlertTriangle size={13} /> CORRECTION
                                </button>
                              </div>
                            </div>
                          ) : (
                            <div className="pt-3 border-t border-gray-200 flex flex-wrap gap-2">
                              <button
                                onClick={() => openDecisionModal(task, 'approve')}
                                className="flex-1 py-2 px-3 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs rounded-xl flex items-center justify-center gap-1.5 shadow-sm transition-colors"
                              >
                                <CheckCircle2 size={14} /> Approve
                              </button>

                              <button
                                onClick={() => openDecisionModal(task, 'request_correction')}
                                className="py-2 px-3 bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-300 font-semibold text-xs rounded-xl flex items-center justify-center gap-1.5 transition-colors"
                                title="Request Author Correction"
                              >
                                <AlertTriangle size={14} /> Correct
                              </button>

                              <button
                                onClick={() => openDecisionModal(task, 'reject')}
                                className="py-2 px-3 bg-rose-50 hover:bg-rose-100 text-rose-800 border border-rose-300 font-semibold text-xs rounded-xl flex items-center justify-center gap-1.5 transition-colors"
                                title="Reject Publication"
                              >
                                <XCircle size={14} /> Reject
                              </button>
                            </div>
                          )
                        ) : (
                          <div className="pt-2 border-t border-gray-200 text-xs text-gray-500 font-medium italic text-center">
                            Under institutional admin review
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* TAB 2: AUDIT TRAIL / HISTORY */}
      {activeTab === 'history' && (
        <div className="space-y-4">
          <div className="bg-white p-6 rounded-2xl border border-gray-200 shadow-sm">
            <h3 className="text-lg font-bold text-gray-900 mb-1 flex items-center gap-2">
              <History className="text-blue-600" size={20} />
              Review Decisions & Immutable Audit Trail
            </h3>
            <p className="text-sm text-gray-500 mb-6">
              Complete historical record of human reviewer decisions, status transitions, reviewer identities, and audit comments.
            </p>

            {historyLoading ? (
              <div className="py-12 text-center text-gray-500">
                <RefreshCw className="animate-spin text-blue-600 mx-auto mb-2" size={28} />
                Loading audit trail records...
              </div>
            ) : historyItems.length === 0 ? (
              <div className="py-12 text-center text-gray-500">
                <FileText className="text-gray-400 mx-auto mb-2" size={32} />
                No resolved review tasks recorded yet. Decisions made in the pending queue will appear here.
              </div>
            ) : (
              <div className="divide-y divide-gray-100">
                {historyItems.map((item) => (
                  <div key={item.id} className="py-4.5 flex flex-col md:flex-row justify-between gap-4">
                    <div className="space-y-1.5">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold uppercase border ${getStatusBadgeClass(item.decision)}`}>
                          {item.decision.replace('_', ' ')}
                        </span>
                        <span className="text-xs font-semibold text-gray-500 bg-gray-100 px-2 py-0.5 rounded">
                          {item.task_type.replace('_', ' ').toUpperCase()}
                        </span>
                        {item.decided_at && (
                          <span className="text-xs text-gray-400">
                            {new Date(item.decided_at).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}
                          </span>
                        )}
                      </div>

                      <h4 className="font-bold text-gray-900 text-sm">
                        {item.entity_title || item.explanation || 'Verified Entity'}
                      </h4>

                      {item.decision_detail?.comment && (
                        <div className="text-xs text-gray-700 bg-gray-50 p-2.5 rounded-lg border border-gray-200 mt-1">
                          <span className="font-semibold text-gray-900">Reviewer Note: </span>
                          "{item.decision_detail.comment}"
                        </div>
                      )}
                    </div>

                    <div className="text-right shrink-0 md:self-center">
                      <div className="text-xs font-bold text-gray-900">{item.reviewer_name}</div>
                      <div className="text-[11px] text-gray-500">{item.reviewer_email}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Decision Modal */}
      {selectedTask && decisionType && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-lg w-full p-6 space-y-5 animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between border-b border-gray-100 pb-3">
              <h3 className="font-extrabold text-lg text-gray-900 flex items-center gap-2">
                {decisionType === 'approve' && (
                  <>
                    <CheckCircle2 className="text-emerald-600" size={22} />
                    {selectedTask.task_type === 'attribution_ambiguous' && !isAdmin
                      ? '✓ Confirm Faculty Attribution (This Is My Publication)'
                      : 'Confirm & Approve Publication'}
                  </>
                )}
                {decisionType === 'reject' && (
                  <>
                    <XCircle className="text-rose-600" size={22} />
                    {selectedTask.task_type === 'attribution_ambiguous' && !isAdmin
                      ? '✕ Reject Attribution (Not My Publication)'
                      : 'Reject Publication Verification'}
                  </>
                )}
                {decisionType === 'request_correction' && (
                  <>
                    <AlertTriangle className="text-amber-600" size={22} /> Request Author Metadata Correction
                  </>
                )}
              </h3>
              <button onClick={closeDecisionModal} className="text-gray-400 hover:text-gray-700 font-bold">
                ✕
              </button>
            </div>

            {/* Target Item summary */}
            <div className="bg-gray-50 p-3.5 rounded-xl border border-gray-200 text-xs space-y-1">
              <p className="font-bold text-gray-900 line-clamp-2">
                {selectedTask.publication?.title || selectedTask.faculty?.name || selectedTask.explanation}
              </p>
              {selectedTask.publication?.doi && (
                <p className="text-gray-500 font-mono">DOI: {selectedTask.publication.doi}</p>
              )}
            </div>

            {/* Decision Status Transition Info */}
            <div className="text-xs text-gray-600 bg-blue-50/60 p-3 rounded-xl border border-blue-200/80">
              <span className="font-bold text-blue-900">Action Effect: </span>
              {decisionType === 'approve' && (
                selectedTask.task_type === 'attribution_ambiguous' && !isAdmin
                  ? 'This publication will be confirmed and linked to your verified faculty profile (Attribution Confidence set to 100%).'
                  : 'Status will transition to HUMAN_VERIFIED (Confidence set to 95%+).'
              )}
              {decisionType === 'reject' && (
                selectedTask.task_type === 'attribution_ambiguous' && !isAdmin
                  ? 'Attribution to your profile will be removed. The publication record will remain preserved in the institutional repository.'
                  : 'Status will transition to HUMAN_REJECTED and flagged in audit log.'
              )}
              {decisionType === 'request_correction' && 'Status will transition to HUMAN_CORRECTED for administrative review.'}
            </div>

            {/* Comment / Note input */}
            <div className="space-y-1.5">
              <label className="text-xs font-bold text-gray-700 uppercase tracking-wider">
                Review Decision Note & Justification:
              </label>
              <textarea
                value={reviewComment}
                onChange={(e) => setReviewComment(e.target.value)}
                placeholder={
                  decisionType === 'approve'
                    ? 'Optional confirmation notes, verification sources checked, etc.'
                    : 'Required: explain why this record is rejected or what metadata correction is requested.'
                }
                rows={3}
                className="w-full p-3 text-xs bg-gray-50 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white text-gray-900"
              />
            </div>

            {/* Modal Actions */}
            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={closeDecisionModal}
                disabled={actionLoading}
                className="px-4 py-2 text-xs font-semibold text-gray-700 hover:bg-gray-100 rounded-xl transition-colors border border-gray-300"
              >
                Cancel
              </button>

              <button
                type="button"
                onClick={submitDecision}
                disabled={actionLoading || (decisionType !== 'approve' && !reviewComment.trim())}
                className={`px-5 py-2 text-xs font-bold text-white rounded-xl shadow-sm transition-colors flex items-center gap-1.5 ${
                  decisionType === 'approve'
                    ? 'bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50'
                    : decisionType === 'reject'
                    ? 'bg-rose-600 hover:bg-rose-700 disabled:opacity-50'
                    : 'bg-amber-600 hover:bg-amber-700 disabled:opacity-50'
                }`}
              >
                {actionLoading ? (
                  <>
                    <RefreshCw className="animate-spin" size={13} /> Processing...
                  </>
                ) : (
                  <>
                    <Send size={13} />
                    {selectedTask.task_type === 'attribution_ambiguous' && !isAdmin
                      ? (decisionType === 'approve' ? 'Confirm This Is My Publication' : decisionType === 'reject' ? 'Confirm Not My Publication' : 'Submit Request')
                      : 'Submit Decision'}
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
