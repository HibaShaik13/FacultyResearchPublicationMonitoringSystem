import { useEffect, useState, useCallback } from 'react';
import api from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import {
  Activity,
  Server,
  Database,
  Layers,
  Cpu,
  RefreshCw,
  Play,
  CheckCircle2,
  Clock,
  ShieldCheck,
  ExternalLink,
  Table,
  CheckCheck
} from 'lucide-react';
import { cleanServiceName } from '../utils/formatters';

interface SystemInfo {
  app_name: string;
  institution: string;
  environment: string;
  version: string;
  status: string;
  server_time: string;
}

interface DatabaseInfo {
  status: string;
  latency_ms: number;
  total_records: number;
  tables: Record<string, number>;
}

interface ProcessingMetrics {
  total_faculty: number;
  total_publications: number;
  verified_publications: number;
  pending_review_tasks: number;
  flagged_risk_records: number;
  total_citations: number;
  verification_rate: number;
}

interface AgentStatusItem {
  id: string;
  name: string;
  phase: number;
  role: string;
  status: string;
  metrics: string;
}

interface ConnectorStatusItem {
  name: string;
  protocol: string;
  endpoint: string;
  status: string;
  purpose: string;
}

interface SyncRunItem {
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

interface AuditLogItem {
  id: string;
  action: string;
  entity_type?: string;
  entity_id?: string;
  user_id?: string;
  ip_address?: string;
  created_at?: string;
  details?: Record<string, any>;
}

interface SystemDiagnostics {
  system: SystemInfo;
  database: DatabaseInfo;
  processing_metrics: ProcessingMetrics;
  agents: AgentStatusItem[];
  connectors: ConnectorStatusItem[];
  sync_history: SyncRunItem[];
}

export default function Monitoring() {
  const { user } = useAuth();

  const [diagnostics, setDiagnostics] = useState<SystemDiagnostics | null>(null);
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'infrastructure' | 'agents' | 'syncs' | 'audit'>('infrastructure');
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncFeedback, setSyncFeedback] = useState<string | null>(null);

  const isAdmin = ['super_admin', 'admin', 'research_admin', 'reviewer'].includes(user?.role || '');

  const fetchDiagnostics = useCallback(async () => {
    setLoading(true);
    try {
      const [diagRes, logRes] = await Promise.all([
        api.get<SystemDiagnostics>('/api/v1/health/system'),
        api.get<{ logs: AuditLogItem[] }>('/api/v1/health/audit-logs?limit=30'),
      ]);
      setDiagnostics(diagRes.data);
      setAuditLogs(logRes.data.logs || []);
    } catch (err) {
      console.error('Failed to load system diagnostics:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDiagnostics();
  }, [fetchDiagnostics]);

  const handleTriggerSync = async () => {
    if (isSyncing) return;
    try {
      setIsSyncing(true);
      setSyncFeedback('Triggering end-to-end multi-agent synchronization cycle...');
      const res = await api.post('/api/v1/agents/sync/run');
      setSyncFeedback(res.data.message || 'Pipeline synchronization completed successfully!');
      await fetchDiagnostics();
      setTimeout(() => setSyncFeedback(null), 5000);
    } catch {
      setSyncFeedback('Pipeline execution encountered an error. Check audit logs.');
      setTimeout(() => setSyncFeedback(null), 5000);
    } finally {
      setIsSyncing(false);
    }
  };

  return (
    <div className="space-y-8 animate-fade-in pb-12">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-200 pb-5">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-gradient-to-tr from-emerald-600 to-teal-600 rounded-xl text-white shadow-md shadow-emerald-500/20">
            <Activity className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">
                System Monitoring & Health Intelligence
              </h1>
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-emerald-50 text-emerald-800 border border-emerald-300">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                {diagnostics?.system.status.toUpperCase() || 'OPERATIONAL'}
              </span>
            </div>
            <p className="text-sm text-slate-600 font-medium mt-0.5">
              Live database telemetry, pipeline health, API throughput, and immutable audit logs.
            </p>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-3">
          {isAdmin && (
            <button
              onClick={handleTriggerSync}
              disabled={isSyncing || loading}
              className="flex items-center gap-2 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-xl shadow-sm transition disabled:opacity-50"
            >
              {isSyncing ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  Synchronizing...
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 fill-white" />
                  Trigger Sync Run
                </>
              )}
            </button>
          )}

          <button
            onClick={() => fetchDiagnostics()}
            disabled={loading}
            className="p-2.5 bg-white border border-slate-200 text-slate-700 rounded-xl hover:bg-slate-50 transition shadow-xs disabled:opacity-50"
            title="Refresh Diagnostics"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-indigo-600' : ''}`} />
          </button>
        </div>
      </div>

      {/* Sync Feedback Message */}
      {syncFeedback && (
        <div className="p-4 bg-indigo-50 border border-indigo-200 rounded-2xl flex items-center gap-3 text-xs font-semibold text-indigo-950 animate-fade-in shadow-xs">
          <CheckCheck className="w-4 h-4 text-indigo-600 shrink-0" />
          <span>{syncFeedback}</span>
        </div>
      )}

      {/* Executive Health KPI Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {/* Database Health */}
        <div className="p-5 bg-white border border-slate-200/90 rounded-2xl shadow-xs hover:shadow-md transition">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Database Engine</span>
            <div className="p-2 bg-emerald-50 text-emerald-600 rounded-xl">
              <Database className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-black text-slate-900 flex items-center gap-2">
            {loading ? '...' : `${diagnostics?.database.latency_ms || 0} ms`}
          </div>
          <div className="text-xs text-emerald-700 font-semibold mt-1 flex items-center gap-1">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>{diagnostics?.database.total_records.toLocaleString() || 0} Total Records</span>
          </div>
        </div>

        {/* Pipeline Ecosystem Status */}
        <div className="p-5 bg-white border border-slate-200/90 rounded-2xl shadow-xs hover:shadow-md transition">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Pipeline Ecosystem</span>
            <div className="p-2 bg-indigo-50 text-indigo-600 rounded-xl">
              <Cpu className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-black text-slate-900">
            {loading ? '...' : `${diagnostics?.agents.length || 13} Services`}
          </div>
          <div className="text-xs text-indigo-700 font-semibold mt-1">
            Active Pipeline Services
          </div>
        </div>

        {/* External Connectors */}
        <div className="p-5 bg-white border border-slate-200/90 rounded-2xl shadow-xs hover:shadow-md transition">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Source Connectors</span>
            <div className="p-2 bg-blue-50 text-blue-600 rounded-xl">
              <Server className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-black text-slate-900">
            {loading ? '...' : `${diagnostics?.connectors.length || 4} / 4`}
          </div>
          <div className="text-xs text-blue-700 font-semibold mt-1">
            OpenAlex, Crossref, S2, ORCID
          </div>
        </div>

        {/* Data Quality & Integrity */}
        <div className="p-5 bg-white border border-slate-200/90 rounded-2xl shadow-xs hover:shadow-md transition">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Integrity Index</span>
            <div className="p-2 bg-purple-50 text-purple-600 rounded-xl">
              <ShieldCheck className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-black text-slate-900">
            {loading ? '...' : `${diagnostics?.processing_metrics.verification_rate || 0}%`}
          </div>
          <div className="text-xs text-purple-700 font-semibold mt-1">
            {diagnostics?.processing_metrics.verified_publications || 0} Verified Works
          </div>
        </div>
      </div>

      {/* Diagnostic Sub-Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-200">
        {[
          { key: 'infrastructure', label: 'Database & Infrastructure', icon: Database },
          { key: 'agents', label: 'Pipeline Services Health', icon: Cpu },
          { key: 'syncs', label: 'Synchronization Cycles', icon: Clock },
          { key: 'audit', label: 'Audit & Activity Log', icon: Layers },
        ].map(tab => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key as any)}
              className={`flex items-center gap-2 px-4 py-3 text-sm font-bold transition-all border-b-2 -mb-px ${
                isActive
                  ? 'border-indigo-600 text-indigo-700 bg-indigo-50/70 rounded-t-lg'
                  : 'border-transparent text-slate-600 hover:text-slate-900'
              }`}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab 1: Database & Infrastructure */}
      {activeTab === 'infrastructure' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Database Tables Telemetry */}
          <div className="p-6 bg-white border border-slate-200 rounded-2xl shadow-xs space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                  <Table className="w-4 h-4 text-indigo-600" />
                  Database Table Record Registry
                </h3>
                <p className="text-xs text-slate-500 font-medium mt-0.5">
                  Live row counts across all managed relational entities.
                </p>
              </div>
              <div className="px-2.5 py-1 text-xs font-bold bg-indigo-50 border border-indigo-200 text-indigo-700 rounded-lg">
                {Object.keys(diagnostics?.database.tables || {}).length} Tables
              </div>
            </div>

            <div className="divide-y divide-slate-100 text-xs">
              {Object.entries(diagnostics?.database.tables || {}).map(([tbl, count]) => (
                <div key={tbl} className="py-2.5 flex items-center justify-between hover:bg-slate-50 px-2.5 rounded-lg transition">
                  <span className="font-mono text-slate-800 font-semibold">{tbl}</span>
                  <span className="font-bold text-slate-900 px-2.5 py-0.5 bg-slate-100 border border-slate-200 rounded-md">
                    {count.toLocaleString()}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* External Bibliographic Connectors */}
          <div className="p-6 bg-white border border-slate-200 rounded-2xl shadow-xs space-y-4 flex flex-col justify-between">
            <div>
              <h3 className="text-base font-bold text-slate-900 flex items-center gap-2 mb-1">
                <Server className="w-4 h-4 text-blue-600" />
                Bibliographic Connector Endpoints
              </h3>
              <p className="text-xs text-slate-500 font-medium mb-4">
                Real external publication APIs and registries integrated into discovery cycles.
              </p>

              <div className="space-y-3">
                {diagnostics?.connectors.map(c => (
                  <div key={c.name} className="p-3.5 bg-slate-50 border border-slate-200 rounded-xl hover:bg-slate-100/60 transition">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-xs text-slate-900">{c.name}</span>
                      <span className="text-[10px] font-bold px-2 py-0.5 bg-emerald-100 text-emerald-800 border border-emerald-300 rounded-full">
                        {c.status.toUpperCase()}
                      </span>
                    </div>
                    <div className="text-[11px] text-slate-600 mt-1 font-medium">{c.purpose}</div>
                    <div className="font-mono text-[10px] text-indigo-700 font-semibold mt-1.5 flex items-center gap-1 truncate">
                      <ExternalLink className="w-3 h-3 shrink-0" /> {c.endpoint}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="p-3.5 bg-indigo-50/80 border border-indigo-200 rounded-xl text-xs text-indigo-900 font-medium mt-4">
              <span className="font-bold text-indigo-950">Institution:</span> {diagnostics?.system.institution} ({diagnostics?.system.environment})
            </div>
          </div>
        </div>
      )}

      {/* Tab 2: Pipeline Services Health */}
      {activeTab === 'agents' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {diagnostics?.agents.map((agent) => (
            <div
              key={agent.id}
              className="p-5 bg-white border border-slate-200 rounded-2xl shadow-xs hover:shadow-md transition space-y-3"
            >
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold px-2.5 py-0.5 bg-indigo-50 border border-indigo-200 text-indigo-700 rounded-lg">
                  Automated Service
                </span>
                <span className={`inline-flex items-center gap-1 text-[11px] font-bold px-2.5 py-0.5 rounded-full border ${
                  agent.status === 'completed' ? 'bg-emerald-100 text-emerald-800 border-emerald-300' :
                  agent.status === 'requires_review' ? 'bg-amber-100 text-amber-800 border-amber-300' :
                  'bg-blue-100 text-blue-800 border-blue-300'
                }`}>
                  <CheckCircle2 className="w-3 h-3" />
                  {agent.status.toUpperCase()}
                </span>
              </div>

              <div>
                <h4 className="text-sm font-bold text-slate-900">{cleanServiceName(agent.name)}</h4>
                <p className="text-xs text-slate-600 font-medium mt-1 leading-relaxed">
                  {agent.role}
                </p>
              </div>

              <div className="pt-2 border-t border-slate-100 text-xs font-semibold text-indigo-700">
                {agent.metrics}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Tab 3: Synchronization Cycles */}
      {activeTab === 'syncs' && (
        <div className="p-6 bg-white border border-slate-200 rounded-2xl shadow-xs space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <Clock className="w-4 h-4 text-indigo-600" />
                Pipeline Synchronization Runs
              </h3>
              <p className="text-xs text-slate-500 font-medium mt-0.5">
                Full end-to-end execution cycles with throughput tracking.
              </p>
            </div>
          </div>

          <div className="overflow-x-auto border border-slate-200 rounded-xl">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-100 text-slate-700 uppercase tracking-wider font-bold border-b border-slate-200">
                <tr>
                  <th className="py-3 px-4">Run Type & ID</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Discovered</th>
                  <th className="py-3 px-4">Merged</th>
                  <th className="py-3 px-4">Verified</th>
                  <th className="py-3 px-4">Review Queue</th>
                  <th className="py-3 px-4">Errors</th>
                  <th className="py-3 px-4">Started At</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {diagnostics?.sync_history.length ? (
                  diagnostics.sync_history.map(s => (
                    <tr key={s.id} className="hover:bg-slate-50 transition">
                      <td className="py-3 px-4">
                        <div className="font-bold text-slate-900">{s.run_type}</div>
                        <div className="font-mono text-[10px] text-slate-500 truncate w-32">{s.id}</div>
                      </td>
                      <td className="py-3 px-4">
                        <span className="px-2 py-0.5 text-[11px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-200 rounded">
                          {s.status.toUpperCase()}
                        </span>
                      </td>
                      <td className="py-3 px-4 font-bold text-indigo-700">
                        {s.publications_discovered}
                      </td>
                      <td className="py-3 px-4 font-bold text-slate-800">
                        {s.publications_merged}
                      </td>
                      <td className="py-3 px-4 font-bold text-emerald-700">
                        {s.publications_verified}
                      </td>
                      <td className="py-3 px-4 font-bold text-amber-700">
                        {s.review_tasks_created}
                      </td>
                      <td className="py-3 px-4 font-bold text-slate-700">
                        {s.errors_count}
                      </td>
                      <td className="py-3 px-4 text-slate-600 font-medium">
                        {s.started_at ? new Date(s.started_at).toLocaleString() : 'N/A'}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={8} className="py-6 text-center text-slate-500 font-medium">
                      No historical sync runs found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 4: Audit & Activity Log */}
      {activeTab === 'audit' && (
        <div className="p-6 bg-white border border-slate-200 rounded-2xl shadow-xs space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <Layers className="w-4 h-4 text-indigo-600" />
                Immutable System Audit Trail
              </h3>
              <p className="text-xs text-slate-500 font-medium mt-0.5">
                Timestamped logging of user review actions, publication edits, and administrative operations.
              </p>
            </div>
            <span className="text-xs font-bold text-slate-600 bg-slate-100 px-2.5 py-1 rounded-lg border border-slate-200">
              {auditLogs.length} Records Loaded
            </span>
          </div>

          <div className="divide-y divide-slate-100">
            {auditLogs.length ? (
              auditLogs.map(log => (
                <div key={log.id} className="py-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-2 hover:bg-slate-50 px-2.5 rounded-xl transition">
                  <div className="flex items-start gap-3">
                    <div className="p-2 bg-indigo-50 border border-indigo-100 text-indigo-600 rounded-xl mt-0.5">
                      <ShieldCheck className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="text-xs font-bold text-slate-900 flex items-center gap-2">
                        <span>{log.action}</span>
                        {log.entity_type && (
                          <span className="px-1.5 py-0.5 bg-slate-100 text-slate-700 border border-slate-200 rounded text-[10px] font-semibold">
                            {log.entity_type}
                          </span>
                        )}
                      </div>
                      <div className="text-[11px] text-slate-600 font-medium mt-0.5">
                        {log.details ? JSON.stringify(log.details) : `Entity ID: ${log.entity_id || 'Global'}`}
                      </div>
                    </div>
                  </div>

                  <div className="text-right text-[11px] text-slate-500 font-medium">
                    <div>{log.created_at ? new Date(log.created_at).toLocaleTimeString() : ''}</div>
                    <div className="text-[10px] text-slate-400">{log.created_at ? new Date(log.created_at).toLocaleDateString() : ''}</div>
                  </div>
                </div>
              ))
            ) : (
              <div className="py-8 text-center text-slate-500 text-xs font-medium">
                No system audit events recorded yet.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
