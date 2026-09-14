import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import {
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
  FileWarning,
  ExternalLink,
  ArrowRight,
  Filter,
  RefreshCw,
  Search,
  Info,
} from 'lucide-react';

interface PublicationItem {
  id: string;
  title: string;
  year?: number;
  doi?: string;
  journal_name?: string;
  risk_level: string;
  risk_reasons?: Record<string, string>;
  verification_status: string;
  metadata_confidence?: number;
  authors?: Array<{ name: string; faculty?: { name: string; department?: string } }>;
}

export default function ResearchIntegrity() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [stats, setStats] = useState<any>({
    none: 0,
    low: 0,
    medium: 0,
    high: 0,
    review_required: 0,
  });
  const [publications, setPublications] = useState<PublicationItem[]>([]);
  const [selectedRiskFilter, setSelectedRiskFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);

  const isFaculty = user?.role === 'faculty' && Boolean(user?.faculty_id);
  const facultyParam = isFaculty ? `?faculty_id=${user.faculty_id}` : '';

  const loadIntegrityData = async () => {
    setLoading(true);
    try {
      const [statsRes, pubsRes] = await Promise.all([
        api.get(`/api/v1/analytics/integrity-stats${facultyParam}`),
        api.get(`/api/v1/publications${facultyParam ? facultyParam + '&limit=50' : '?limit=50'}`),
      ]);

      setStats(statsRes.data || {});
      const pubsData = Array.isArray(pubsRes.data) ? pubsRes.data : pubsRes.data?.data || [];
      setPublications(pubsData);
    } catch (err) {
      console.error('Failed to load integrity data', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadIntegrityData();
  }, [user]);

  // Filter publications
  const filteredPubs = publications.filter((p) => {
    const matchesRisk =
      selectedRiskFilter === 'all'
        ? true
        : selectedRiskFilter === 'flagged'
        ? (p.risk_level && p.risk_level !== 'none') || p.verification_status === 'needs_review'
        : p.risk_level === selectedRiskFilter;

    const matchesSearch =
      !searchQuery.trim() ||
      p.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (p.doi && p.doi.toLowerCase().includes(searchQuery.toLowerCase()));

    return matchesRisk && matchesSearch;
  });

  const getRiskBadge = (level?: string) => {
    switch (level?.toLowerCase()) {
      case 'high':
        return 'bg-red-100 text-red-800 border-red-300 font-bold';
      case 'medium':
        return 'bg-amber-100 text-amber-800 border-amber-300 font-semibold';
      case 'low':
        return 'bg-blue-100 text-blue-800 border-blue-200';
      default:
        return 'bg-emerald-100 text-emerald-800 border-emerald-200 font-medium';
    }
  };

  return (
    <div className="space-y-6 pb-12 font-sans">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-white p-6 rounded-2xl border border-gray-200/80 shadow-sm">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2.5 py-0.5 rounded-full text-xs font-bold uppercase tracking-wider bg-rose-100 text-rose-800">
              Research Integrity
            </span>
            <span className="text-xs text-gray-500 font-medium">Quality Assurance & Risk Auditing</span>
          </div>
          <h1 className="text-2xl font-extrabold text-gray-900 mt-2 flex items-center gap-2">
            <ShieldAlert className="text-blue-600" size={28} />
            Research Integrity & Quality Dashboard
          </h1>
          <p className="text-sm text-gray-600 mt-1">
            Continuous automated screening for predatory venues, metadata inconsistencies, DOI conflicts, and citation anomalies.
          </p>
        </div>

        <button
          onClick={loadIntegrityData}
          className="px-4 py-2 bg-gray-50 hover:bg-gray-100 text-gray-700 border border-gray-200 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-colors shadow-sm"
        >
          <RefreshCw size={13} className={loading ? 'animate-spin' : ''} /> Refresh Audit
        </button>
      </div>

      {/* 4 Risk Status Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Low / None Risk */}
        <div
          onClick={() => setSelectedRiskFilter('low')}
          className={`stat-card p-5 bg-white border rounded-2xl shadow-sm cursor-pointer transition-all ${
            selectedRiskFilter === 'low' ? 'border-emerald-500 ring-2 ring-emerald-100' : 'border-gray-200 hover:border-emerald-300'
          }`}
        >
          <div className="flex items-center justify-between">
            <p className="text-xs font-bold text-gray-500 uppercase tracking-wider">Low / Verified Safe</p>
            <ShieldCheck size={20} className="text-emerald-500" />
          </div>
          <h3 className="text-3xl font-black text-gray-900 mt-2">{(stats.low || 0) + (stats.none || 0)}</h3>
          <p className="text-xs text-emerald-600 font-semibold mt-1">Zero critical anomalies</p>
        </div>

        {/* Medium Risk */}
        <div
          onClick={() => setSelectedRiskFilter('medium')}
          className={`stat-card p-5 bg-white border rounded-2xl shadow-sm cursor-pointer transition-all ${
            selectedRiskFilter === 'medium' ? 'border-amber-500 ring-2 ring-amber-100' : 'border-gray-200 hover:border-amber-300'
          }`}
        >
          <div className="flex items-center justify-between">
            <p className="text-xs font-bold text-gray-500 uppercase tracking-wider">Medium Risk</p>
            <AlertTriangle size={20} className="text-amber-500" />
          </div>
          <h3 className="text-3xl font-black text-gray-900 mt-2">{stats.medium || 0}</h3>
          <p className="text-xs text-amber-600 font-semibold mt-1">Metadata or year variation</p>
        </div>

        {/* High Risk */}
        <div
          onClick={() => setSelectedRiskFilter('high')}
          className={`stat-card p-5 bg-white border rounded-2xl shadow-sm cursor-pointer transition-all ${
            selectedRiskFilter === 'high' ? 'border-red-500 ring-2 ring-red-100' : 'border-gray-200 hover:border-red-300'
          }`}
        >
          <div className="flex items-center justify-between">
            <p className="text-xs font-bold text-gray-500 uppercase tracking-wider">High Risk</p>
            <ShieldAlert size={20} className="text-red-500" />
          </div>
          <h3 className="text-3xl font-black text-gray-900 mt-2">{stats.high || 0}</h3>
          <p className="text-xs text-red-600 font-semibold mt-1">Venue or title contradiction</p>
        </div>

        {/* Review Required */}
        <div
          onClick={() => navigate('/verification')}
          className="stat-card p-5 bg-white border border-blue-200 hover:border-blue-400 rounded-2xl shadow-sm cursor-pointer transition-all group"
        >
          <div className="flex items-center justify-between">
            <p className="text-xs font-bold text-blue-700 uppercase tracking-wider">Verification Queue</p>
            <ArrowRight size={20} className="text-blue-600 group-hover:translate-x-1 transition-transform" />
          </div>
          <h3 className="text-3xl font-black text-blue-900 mt-2">{stats.review_required || 0}</h3>
          <p className="text-xs text-blue-600 font-semibold mt-1 flex items-center gap-1">
            Open human review queue →
          </p>
        </div>
      </div>

      {/* Automated Integrity Framework Explainer */}
      <div className="bg-gradient-to-r from-blue-900 to-indigo-950 rounded-2xl p-6 text-white shadow-md">
        <div className="flex items-center gap-2 mb-2">
          <Info size={18} className="text-blue-300" />
          <h3 className="font-bold text-base text-white">Automated Integrity & Verification Protocol</h3>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4 text-xs text-blue-100">
          <div className="bg-white/10 p-3.5 rounded-xl border border-white/10">
            <span className="font-bold text-white block mb-1">1. DOI & Crossref Validation</span>
            Every publication DOI is validated for correct syntax and cross-referenced with Crossref API to confirm genuine publication container and date.
          </div>
          <div className="bg-white/10 p-3.5 rounded-xl border border-white/10">
            <span className="font-bold text-white block mb-1">2. Multi-Source Consistency</span>
            Discovered titles and years are compared across OpenAlex, Semantic Scholar, and institutional records to detect title discrepancies.
          </div>
          <div className="bg-white/10 p-3.5 rounded-xl border border-white/10">
            <span className="font-bold text-white block mb-1">3. Institutional Attribution</span>
            Author names and institutional affiliations are cross-checked against VFSTR faculty identity profiles to prevent misattributions.
          </div>
        </div>
      </div>

      {/* Flagged Publications & Quality Assurance List */}
      <div className="bg-white p-6 rounded-2xl border border-gray-200 shadow-sm space-y-4">
        <div className="flex flex-col md:flex-row justify-between items-stretch md:items-center gap-3">
          <div>
            <h3 className="text-lg font-bold text-gray-900 flex items-center gap-2">
              <FileWarning className="text-blue-600" size={20} />
              Publication Quality Audit Records
            </h3>
            <p className="text-xs text-gray-500">
              Inspecting {filteredPubs.length} publications for risk signals, missing identifiers, or metadata variations
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={14} />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Filter by title or DOI..."
                className="pl-8 pr-3 py-1.5 text-xs bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 text-gray-900"
              />
            </div>

            <div className="flex items-center gap-1.5 text-xs">
              <Filter size={13} className="text-gray-400" />
              <select
                value={selectedRiskFilter}
                onChange={(e) => setSelectedRiskFilter(e.target.value)}
                className="bg-gray-50 border border-gray-200 text-gray-700 rounded-lg px-2.5 py-1.5 font-medium focus:outline-none"
              >
                <option value="all">All Records</option>
                <option value="flagged">Flagged Only</option>
                <option value="low">Low Risk</option>
                <option value="medium">Medium Risk</option>
                <option value="high">High Risk</option>
              </select>
            </div>
          </div>
        </div>

        {/* Publication Cards / Table */}
        {loading ? (
          <div className="py-12 text-center text-gray-500">
            <RefreshCw className="animate-spin text-blue-600 mx-auto mb-2" size={28} />
            Loading integrity records...
          </div>
        ) : filteredPubs.length === 0 ? (
          <div className="py-12 text-center text-gray-500 bg-gray-50 rounded-xl border border-gray-200">
            <CheckCircle2 className="text-emerald-500 mx-auto mb-2" size={32} />
            <h4 className="font-bold text-gray-900 text-sm">No Integrity Issues Found</h4>
            <p className="text-xs text-gray-500 mt-1">No publications match the selected risk filter criteria.</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {filteredPubs.slice(0, 15).map((pub) => {
              const reasonsList = pub.risk_reasons ? Object.entries(pub.risk_reasons) : [];
              return (
                <div key={pub.id} className="py-4 flex flex-col md:flex-row justify-between gap-4 hover:bg-gray-50/50 p-2 rounded-xl transition-colors">
                  <div className="space-y-1.5 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className={`px-2 py-0.5 rounded-lg text-xs border ${getRiskBadge(pub.risk_level)}`}>
                        RISK: {(pub.risk_level || 'NONE').toUpperCase()}
                      </span>
                      <span className="text-xs font-semibold bg-gray-100 text-gray-700 px-2 py-0.5 rounded border border-gray-200">
                        STATUS: {pub.verification_status.replace('_', ' ').toUpperCase()}
                      </span>
                      {pub.year && (
                        <span className="text-xs text-gray-500 font-medium">Year: {pub.year}</span>
                      )}
                    </div>

                    <h4 className="font-bold text-gray-900 text-sm leading-snug">{pub.title}</h4>

                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-500">
                      {pub.journal_name && (
                        <span className="italic text-gray-700 truncate max-w-xs">{pub.journal_name}</span>
                      )}
                      {pub.doi ? (
                        <span className="font-mono text-blue-600 bg-blue-50 px-2 py-0.5 rounded border border-blue-200 inline-flex items-center gap-1">
                          DOI: {pub.doi} <ExternalLink size={10} />
                        </span>
                      ) : (
                        <span className="text-amber-700 font-medium bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                          Missing DOI Identifier
                        </span>
                      )}
                    </div>

                    {/* Detected Risk Reasons */}
                    {reasonsList.length > 0 && (
                      <div className="pt-1">
                        <div className="bg-amber-50/80 border border-amber-200/90 rounded-lg p-2.5 text-xs text-amber-900 space-y-1">
                          <span className="font-bold block">Integrity Signals Detected:</span>
                          <ul className="list-disc list-inside space-y-0.5 text-[11px] text-amber-800">
                            {reasonsList.map(([key, val], idx) => (
                              <li key={idx}>
                                <strong>{key.replace('_', ' ')}:</strong> {val}
                              </li>
                            ))}
                          </ul>
                        </div>
                      </div>
                    )}
                  </div>

                  <div className="self-start md:self-center shrink-0">
                    <button
                      onClick={() => navigate('/verification')}
                      className="px-3 py-1.5 text-xs font-semibold text-blue-700 bg-blue-50 hover:bg-blue-100 border border-blue-200 rounded-xl flex items-center gap-1.5 transition-colors shadow-sm"
                    >
                      Audit Record <ArrowRight size={12} />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
