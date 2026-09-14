import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import {
  Activity,
  Play,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  Clock,
  ShieldCheck,
  Users,
  BookOpen,
  TrendingUp,
  ChevronRight,
  Database,
  Workflow,
  Sparkles,
} from 'lucide-react';
import { cleanServiceName } from '../utils/formatters';

interface AgentInfo {
  id: string;
  name: string;
  phase: number;
  role: string;
  status: 'completed' | 'running' | 'requires_review' | 'failed' | 'idle';
  metrics?: string;
}

interface SystemHealth {
  faculty_count: number;
  publications_count: number;
  verified_count: number;
  pending_reviews_count: number;
  total_citations: number;
  verification_integrity_rate: string;
  pipeline_status: string;
}

interface SyncRunInfo {
  id: string;
  run_type: string;
  status: string;
  trigger?: string;
  publications_discovered: number;
  publications_merged: number;
  publications_verified: number;
  review_tasks_created: number;
  errors_count: number;
  started_at: string;
  completed_at?: string;
}

export default function ResearchPipeline() {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [syncRuns, setSyncRuns] = useState<SyncRunInfo[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);
  const { user } = useAuth();
  const navigate = useNavigate();

  const isAdmin = user?.role === 'admin' || user?.role === 'research_admin' || user?.role === 'reviewer';

  const fetchData = async () => {
    try {
      setIsLoading(true);
      const [statusRes, runsRes] = await Promise.all([
        api.get('/api/v1/agents/status'),
        api.get('/api/v1/agents/sync-runs?limit=10'),
      ]);

      setAgents(statusRes.data.agents || []);
      setHealth(statusRes.data.system_health || null);
      setSyncRuns(runsRes.data.data || []);
    } catch (err) {
      console.error('Failed to fetch pipeline status:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleTriggerSync = async () => {
    if (isSyncing) return;
    try {
      setIsSyncing(true);
      setSyncMessage('Orchestrating end-to-end sync across all 13 agents...');
      const res = await api.post('/api/v1/agents/sync/run');
      setSyncMessage(res.data.message || 'Pipeline synchronization completed successfully!');
      await fetchData();
    } catch (err: any) {
      setSyncMessage('Pipeline run encountered an issue. Check audit logs.');
    } finally {
      setIsSyncing(false);
      setTimeout(() => setSyncMessage(null), 5000);
    }
  };

  return (
    <div className="space-y-8 max-w-7xl mx-auto pb-12 font-sans">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white/90 backdrop-blur-md p-6 rounded-3xl border border-slate-200/80 shadow-sm">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="w-10 h-10 rounded-2xl bg-blue-600 flex items-center justify-center text-white shadow-md shadow-blue-600/20">
              <Workflow size={22} />
            </div>
            <div>
              <h1 className="text-xl sm:text-2xl font-black text-slate-900 tracking-tight">
                Multi-Agent Research Pipeline
              </h1>
              <p className="text-xs sm:text-sm text-slate-500 font-medium">
                End-to-End Orchestration & Verification Lifecycle
              </p>
            </div>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-3">
          <button
            onClick={fetchData}
            disabled={isLoading || isSyncing}
            className="flex items-center gap-1.5 px-4 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-bold transition-all disabled:opacity-50 cursor-pointer"
          >
            <RefreshCw size={14} className={isLoading ? 'animate-spin' : ''} />
            <span>Refresh</span>
          </button>

          {isAdmin && (
            <button
              onClick={handleTriggerSync}
              disabled={isSyncing}
              className="flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white rounded-xl text-xs font-bold shadow-md shadow-blue-600/25 transition-all disabled:opacity-50 cursor-pointer"
            >
              {isSyncing ? (
                <>
                  <RefreshCw size={15} className="animate-spin" />
                  <span>Syncing Pipeline Services...</span>
                </>
              ) : (
                <>
                  <Play size={15} />
                  <span>Run Full Pipeline Sync</span>
                </>
              )}
            </button>
          )}
        </div>
      </div>

      {/* Live Sync Notification Banner */}
      {syncMessage && (
        <div className="p-4 bg-blue-50 border border-blue-200 text-blue-800 rounded-2xl text-xs font-semibold flex items-center justify-between shadow-sm animate-in fade-in">
          <div className="flex items-center gap-2">
            <Sparkles size={16} className="text-blue-600" />
            <span>{syncMessage}</span>
          </div>
          {isSyncing && <RefreshCw size={14} className="animate-spin text-blue-600" />}
        </div>
      )}

      {/* System Health & Throughput KPI Cards */}
      {health && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
          <div className="bg-white/80 backdrop-blur-md p-4 rounded-2xl border border-slate-200/80 shadow-xs">
            <div className="flex items-center justify-between text-slate-400 mb-1">
              <span className="text-[11px] font-bold uppercase tracking-wider">Faculty</span>
              <Users size={16} className="text-blue-600" />
            </div>
            <div className="text-xl font-black text-slate-900">{health.faculty_count}</div>
            <div className="text-[10px] text-slate-500 font-medium">Profiles Active</div>
          </div>

          <div className="bg-white/80 backdrop-blur-md p-4 rounded-2xl border border-slate-200/80 shadow-xs">
            <div className="flex items-center justify-between text-slate-400 mb-1">
              <span className="text-[11px] font-bold uppercase tracking-wider">Publications</span>
              <BookOpen size={16} className="text-indigo-600" />
            </div>
            <div className="text-xl font-black text-slate-900">{health.publications_count}</div>
            <div className="text-[10px] text-slate-500 font-medium">Discovered Works</div>
          </div>

          <div className="bg-white/80 backdrop-blur-md p-4 rounded-2xl border border-slate-200/80 shadow-xs">
            <div className="flex items-center justify-between text-slate-400 mb-1">
              <span className="text-[11px] font-bold uppercase tracking-wider">Verified</span>
              <CheckCircle2 size={16} className="text-emerald-600" />
            </div>
            <div className="text-xl font-black text-emerald-700">{health.verified_count}</div>
            <div className="text-[10px] text-emerald-600 font-bold">Consensus Approved</div>
          </div>

          <div className="bg-white/80 backdrop-blur-md p-4 rounded-2xl border border-slate-200/80 shadow-xs">
            <div className="flex items-center justify-between text-slate-400 mb-1">
              <span className="text-[11px] font-bold uppercase tracking-wider">Integrity</span>
              <ShieldCheck size={16} className="text-sky-600" />
            </div>
            <div className="text-xl font-black text-sky-700">{health.verification_integrity_rate}</div>
            <div className="text-[10px] text-slate-500 font-medium">Confidence Score</div>
          </div>

          <div className="bg-white/80 backdrop-blur-md p-4 rounded-2xl border border-slate-200/80 shadow-xs">
            <div className="flex items-center justify-between text-slate-400 mb-1">
              <span className="text-[11px] font-bold uppercase tracking-wider">Citations</span>
              <TrendingUp size={16} className="text-purple-600" />
            </div>
            <div className="text-xl font-black text-slate-900">{health.total_citations}</div>
            <div className="text-[10px] text-slate-500 font-medium">Multi-Source Total</div>
          </div>

          <div
            onClick={() => navigate('/verification')}
            className="bg-white/80 backdrop-blur-md p-4 rounded-2xl border border-slate-200/80 shadow-xs hover:border-amber-400 cursor-pointer transition-all"
          >
            <div className="flex items-center justify-between text-slate-400 mb-1">
              <span className="text-[11px] font-bold uppercase tracking-wider">Human Queue</span>
              <AlertTriangle size={16} className={health.pending_reviews_count > 0 ? 'text-amber-500' : 'text-slate-400'} />
            </div>
            <div className="text-xl font-black text-amber-600">{health.pending_reviews_count}</div>
            <div className="text-[10px] text-amber-700 font-semibold flex items-center gap-0.5">
              <span>Review Tasks</span> <ChevronRight size={10} />
            </div>
          </div>
        </div>
      )}

      {/* 13-Agent Orchestration Sequence Grid */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
            <Activity size={18} className="text-blue-600" /> Autonomous Execution Flow
          </h2>
          <span className="text-xs text-slate-500 font-medium">
            All Services Connected & Operational
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {agents.map((agent) => {
            const isReviewAgent = agent.id === 'agent-10' && health && health.pending_reviews_count > 0;
            return (
              <div
                key={agent.id || agent.name}
                className={`bg-white/90 backdrop-blur-md p-5 rounded-2xl border shadow-xs transition-all ${
                  isReviewAgent
                    ? 'border-amber-300 hover:border-amber-400 bg-amber-50/20'
                    : 'border-slate-200/80 hover:border-blue-300 hover:shadow-md'
                }`}
              >
                <div className="flex items-start justify-between gap-2 mb-3">
                  <div className="flex items-center gap-2.5">
                    <div className="w-7 h-7 rounded-xl bg-blue-50 border border-blue-200 text-blue-700 font-black text-xs flex items-center justify-center shadow-2xs">
                      <Activity size={13} className="text-blue-600" />
                    </div>
                    <div>
                      <h3 className="font-bold text-sm text-slate-900">{cleanServiceName(agent.name)}</h3>
                      <span className="text-[10px] font-semibold text-slate-400">Pipeline Service</span>
                    </div>
                  </div>

                  {/* Status Badge */}
                  {isReviewAgent ? (
                    <span className="flex items-center gap-1 text-[10px] font-extrabold text-amber-700 bg-amber-100 border border-amber-300 px-2 py-0.5 rounded-full">
                      <AlertTriangle size={10} /> Needs Review
                    </span>
                  ) : agent.status === 'completed' ? (
                    <span className="flex items-center gap-1 text-[10px] font-extrabold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-full">
                      <CheckCircle2 size={10} /> Active
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-[10px] font-extrabold text-slate-600 bg-slate-100 px-2 py-0.5 rounded-full">
                      <Clock size={10} /> Standby
                    </span>
                  )}
                </div>

                <p className="text-xs text-slate-600 leading-relaxed font-normal min-h-[36px]">
                  {agent.role}
                </p>

                {agent.metrics && (
                  <div className="mt-3 pt-2.5 border-t border-slate-100 flex items-center justify-between text-[11px]">
                    <span className="text-slate-400 font-medium">Throughput:</span>
                    <span className="font-bold text-slate-800 flex items-center gap-1">
                      <Database size={11} className="text-blue-600" /> {agent.metrics}
                    </span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Sync Execution & Audit Log History Table */}
      <div className="bg-white/90 backdrop-blur-md rounded-3xl p-6 border border-slate-200/80 shadow-sm space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-bold text-slate-900">Pipeline Synchronization Runs</h2>
            <p className="text-xs text-slate-500 font-medium mt-0.5">
              Auditable execution log with input/output statistics across all synchronization cycles
            </p>
          </div>
          <span className="text-xs font-semibold text-slate-400">Showing last {syncRuns.length} runs</span>
        </div>

        {syncRuns.length === 0 ? (
          <div className="p-8 text-center text-slate-400 text-xs">
            No pipeline runs logged yet. Click &quot;Run Full Pipeline Sync&quot; to execute the multi-agent cycle.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50/80 text-slate-500 font-bold border-b border-slate-200">
                <tr>
                  <th className="p-3">Run ID</th>
                  <th className="p-3">Type / Trigger</th>
                  <th className="p-3">Status</th>
                  <th className="p-3 text-center">Discovered</th>
                  <th className="p-3 text-center">Merged</th>
                  <th className="p-3 text-center">Verified</th>
                  <th className="p-3 text-center">Review Tasks</th>
                  <th className="p-3 text-right">Started At</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {syncRuns.map((r) => (
                  <tr key={r.id} className="hover:bg-slate-50/50 transition-colors">
                    <td className="p-3 font-mono font-bold text-blue-700">
                      {r.id ? `${r.id.slice(0, 8)}...` : 'N/A'}
                    </td>
                    <td className="p-3">
                      <span className="font-semibold text-slate-900 capitalize">{r.run_type.replace('_', ' ')}</span>
                      <span className="text-[10px] text-slate-400 block">{r.trigger || 'manual'}</span>
                    </td>
                    <td className="p-3">
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                          r.status === 'completed'
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                            : r.status === 'running'
                            ? 'bg-blue-50 text-blue-700 border border-blue-200 animate-pulse'
                            : 'bg-rose-50 text-rose-700 border border-rose-200'
                        }`}
                      >
                        {r.status}
                      </span>
                    </td>
                    <td className="p-3 text-center font-semibold">{r.publications_discovered || 0}</td>
                    <td className="p-3 text-center font-semibold">{r.publications_merged || 0}</td>
                    <td className="p-3 text-center font-semibold text-emerald-700">{r.publications_verified || 0}</td>
                    <td className="p-3 text-center font-semibold text-amber-600">{r.review_tasks_created || 0}</td>
                    <td className="p-3 text-right text-slate-500">
                      {r.started_at ? new Date(r.started_at).toLocaleString() : 'N/A'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
