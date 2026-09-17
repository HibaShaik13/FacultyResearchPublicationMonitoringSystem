import { useEffect, useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import api from '../services/api';
import {
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
  RefreshCw,
  Trash2,
  Edit3,
  Plus,
  BookOpen,
  Award,
  Building2,
  Mail,
  Layers,
  Database,
  Search,
  Sparkles,
  Link2,
} from 'lucide-react';

interface IdentifierItem {
  id: string | null;
  type: string;
  name: string;
  value: string | null;
  profile_url: string | null;
  verified: boolean;
  status: 'VERIFIED' | 'AMBIGUOUS' | 'INVALID' | 'NOT_FOUND' | 'NOT_CONNECTED';
  identity_status?: string;
  live_api_status?: string;
  ingestion_status?: string;
  confidence: number;
  verification_source: string | null;
  last_verified_at: string | null;
  created_at: string | null;
  is_connected: boolean;
  placeholder?: string;
  description?: string;
}

interface IdentifiersStatusResponse {
  faculty_id: string;
  has_connected_identifiers: boolean;
  connected_count: number;
  total_supported: number;
  identifiers: IdentifierItem[];
}

export default function MyProfile() {
  const { user } = useAuth();
  const [profile, setProfile] = useState<any>(null);
  const [identifiersData, setIdentifiersData] = useState<IdentifiersStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);
  const [editingType, setEditingType] = useState<string | null>(null);
  const [inputValue, setInputValue] = useState<string>('');
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Onboarding form state for first-time users
  const [onboardingInputs, setOnboardingInputs] = useState<Record<string, string>>({
    scopus: '',
    ieee: '',
    openalex: '',
    orcid: '',
    semantic_scholar: '',
    vidwan: '',
  });

  const loadProfileData = async () => {
    try {
      setLoading(true);
      const [profRes, identsRes] = await Promise.all([
        api.get('/api/v1/faculty/me'),
        api.get('/api/v1/faculty/me/identifiers').catch(() => ({ data: null })),
      ]);
      setProfile(profRes.data);
      if (identsRes?.data) {
        setIdentifiersData(identsRes.data);
      }
    } catch (err: any) {
      console.error('Failed to load profile details:', err);
      if (err.response?.status === 404) {
        setProfile(null);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (user) {
      loadProfileData();
    }
  }, [user]);

  const handleSaveOnboarding = async (e: React.FormEvent) => {
    e.preventDefault();
    const toSave = Object.entries(onboardingInputs)
      .filter(([_, val]) => val.trim().length > 0)
      .map(([type, val]) => ({ type, value: val.trim() }));

    if (toSave.length === 0) {
      setFeedback({ type: 'error', text: 'Please enter at least one external researcher identifier.' });
      return;
    }

    try {
      setSaving(true);
      setFeedback(null);
      await api.post('/api/v1/faculty/me/identifiers', { identifiers: toSave });
      setFeedback({ type: 'success', text: 'Identifiers saved and verified successfully!' });
      await loadProfileData();
    } catch (err: any) {
      setFeedback({ type: 'error', text: err.response?.data?.detail || 'Failed to save identifiers.' });
    } finally {
      setSaving(false);
    }
  };

  const handleSaveSingleIdentifier = async (type: string) => {
    if (!inputValue.trim()) return;
    try {
      setSaving(true);
      setFeedback(null);
      await api.post('/api/v1/faculty/me/identifiers', {
        identifiers: [{ type, value: inputValue.trim() }],
      });
      setFeedback({ type: 'success', text: `${type.toUpperCase()} identifier updated and verified.` });
      setEditingType(null);
      setInputValue('');
      await loadProfileData();
    } catch (err: any) {
      setFeedback({ type: 'error', text: err.response?.data?.detail || 'Failed to update identifier.' });
    } finally {
      setSaving(false);
    }
  };

  const handleReverify = async (type: string) => {
    try {
      setSaving(true);
      setFeedback(null);
      await api.post(`/api/v1/faculty/me/identifiers/${type}/verify`);
      setFeedback({ type: 'success', text: `${type.toUpperCase()} re-verified successfully.` });
      await loadProfileData();
    } catch (err: any) {
      setFeedback({ type: 'error', text: err.response?.data?.detail || 'Re-verification failed.' });
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteIdentifier = async (type: string) => {
    if (!window.confirm(`Are you sure you want to disconnect your ${type.toUpperCase()} identifier?`)) return;
    try {
      setSaving(true);
      setFeedback(null);
      await api.delete(`/api/v1/faculty/me/identifiers/${type}`);
      setFeedback({ type: 'success', text: `${type.toUpperCase()} identifier disconnected.` });
      await loadProfileData();
    } catch (err: any) {
      setFeedback({ type: 'error', text: err.response?.data?.detail || 'Failed to delete identifier.' });
    } finally {
      setSaving(false);
    }
  };

  const handleTriggerSync = async () => {
    try {
      setSyncing(true);
      setSyncMessage(null);
      const res = await api.post('/api/v1/faculty/me/sync');
      setSyncMessage(res.data.message || 'Sync completed successfully.');
      await loadProfileData();
    } catch (err: any) {
      setSyncMessage(err.response?.data?.detail || 'Failed to sync research publications.');
    } finally {
      setSyncing(false);
    }
  };

  if (profile?.admin) {
    return (
      <div className="space-y-6">
        <div className="stat-card p-8 bg-white/90 border border-gray-200/80 rounded-2xl shadow-sm">
          <div className="flex items-center gap-3 mb-3">
            <ShieldCheck className="w-8 h-8 text-indigo-600" />
            <h2 className="text-2xl font-bold text-gray-900">Institutional Administrator Profile</h2>
          </div>
          <p className="text-indigo-600 font-semibold text-sm">Role: {user?.role?.toUpperCase()} • {user?.email}</p>
          <p className="text-gray-500 text-xs mt-2 leading-relaxed">
            As an institutional administrator, your account possesses cross-departmental administrative authority, full verification queue review privileges, and global reporting capabilities.
          </p>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center p-16 space-y-3">
        <RefreshCw className="w-8 h-8 text-indigo-600 animate-spin" />
        <p className="text-sm font-medium text-gray-500">Loading unified research identity...</p>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="p-8 text-center bg-white border border-gray-200 rounded-2xl shadow-sm">
        <AlertCircle className="w-10 h-10 text-amber-500 mx-auto mb-2" />
        <p className="text-gray-700 font-semibold">Faculty Profile Not Found</p>
        <p className="text-xs text-gray-400 mt-1">Please contact your institutional administrator to bind your user account ({user?.email}).</p>
      </div>
    );
  }

  const latestMetrics = profile.metric_snapshot || {};
  const hasConnectedIds = identifiersData?.has_connected_identifiers ?? false;
  const allVerified = identifiersData?.identifiers.filter(i => i.is_connected).every(i => i.verified) ?? false;

  return (
    <div className="space-y-8 max-w-7xl mx-auto pb-12">
      {/* Toast Feedback */}
      {feedback && (
        <div
          className={`p-4 rounded-xl text-sm font-medium flex items-center justify-between shadow-sm transition-all ${
            feedback.type === 'success' ? 'bg-emerald-50 text-emerald-800 border border-emerald-200' : 'bg-rose-50 text-rose-800 border border-rose-200'
          }`}
        >
          <div className="flex items-center gap-2">
            {feedback.type === 'success' ? <CheckCircle2 className="w-5 h-5 text-emerald-600" /> : <AlertCircle className="w-5 h-5 text-rose-600" />}
            <span>{feedback.text}</span>
          </div>
          <button onClick={() => setFeedback(null)} className="text-xs opacity-70 hover:opacity-100 font-bold">✕</button>
        </div>
      )}

      {/* ========================================================================= */}
      {/* SECTION A: FACULTY IDENTITY HEADER & TRUST BADGE                          */}
      {/* ========================================================================= */}
      <div className="stat-card p-8 bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white rounded-3xl shadow-xl relative overflow-hidden">
        <div className="absolute right-0 top-0 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />
        
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 relative z-10">
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <span className="px-2.5 py-1 bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 text-[11px] font-bold rounded-full uppercase tracking-wider">
                {profile.designation || 'Faculty Member'}
              </span>
              {allVerified && hasConnectedIds && (
                <span className="flex items-center gap-1.5 px-3 py-1 bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-[11px] font-bold rounded-full">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" /> Verified Institutional Identity
                </span>
              )}
            </div>

            <h1 className="text-3xl font-extrabold tracking-tight text-white">
              {profile.title_prefix || 'Dr.'} {profile.raw_name}
            </h1>

            <div className="flex flex-wrap items-center gap-y-1 gap-x-4 text-xs text-slate-300">
              <span className="flex items-center gap-1.5 font-medium">
                <Building2 className="w-4 h-4 text-indigo-400" />
                Department of {profile.department} • Vignan's Foundation for Science, Technology & Research (VFSTR)
              </span>
              <span className="flex items-center gap-1.5 font-mono text-slate-400">
                <Mail className="w-4 h-4 text-indigo-400" />
                {profile.institutional_email || profile.raw_email}
              </span>
            </div>
          </div>

          {/* Sync Trigger Action */}
          <div className="flex flex-col sm:flex-row gap-3">
            <button
              onClick={handleTriggerSync}
              disabled={syncing || !hasConnectedIds}
              className="flex items-center justify-center gap-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-700 disabled:text-slate-400 text-white font-semibold text-xs rounded-xl shadow-md transition-all active:scale-95 cursor-pointer disabled:cursor-not-allowed"
            >
              <RefreshCw className={`w-4 h-4 ${syncing ? 'animate-spin' : ''}`} />
              {syncing ? 'Synchronizing Publications...' : 'Sync Research Publications'}
            </button>
          </div>
        </div>

        {syncMessage && (
          <div className="mt-4 p-3 bg-white/10 border border-white/15 rounded-xl text-xs text-indigo-200 flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-indigo-300 shrink-0" />
            <span>{syncMessage}</span>
          </div>
        )}
      </div>

      {/* ========================================================================= */}
      {/* SECTION B: FIRST-TIME ONBOARDING OR RETURNING EXTERNAL IDENTIFIERS         */}
      {/* ========================================================================= */}
      {!hasConnectedIds ? (
        /* FIRST-TIME EXPERIENCE: Onboarding Card */
        <div className="stat-card p-8 bg-gradient-to-b from-indigo-50/70 to-white border-2 border-dashed border-indigo-200 rounded-3xl shadow-sm">
          <div className="max-w-3xl">
            <div className="flex items-center gap-2.5 text-indigo-700 font-bold text-lg mb-1">
              <Link2 className="w-5 h-5" />
              <h2>Connect Your Research Profiles</h2>
            </div>
            <p className="text-gray-600 text-xs leading-relaxed mb-6">
              Add your external researcher identifiers <strong>once</strong>. We will verify them against legitimate scholarly sources and use them to automatically discover, deduplicate, and continuously synchronize your publications.
            </p>

            <form onSubmit={handleSaveOnboarding} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold text-gray-700 mb-1">
                    Scopus Author ID
                  </label>
                  <input
                    type="text"
                    value={onboardingInputs.scopus}
                    onChange={(e) => setOnboardingInputs({ ...onboardingInputs, scopus: e.target.value })}
                    placeholder="e.g. 54788460700"
                    className="w-full px-3.5 py-2.5 bg-white border border-gray-300 rounded-xl text-xs font-mono focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
                  />
                  <span className="text-[10px] text-gray-400 mt-0.5 block">Elsevier Scopus Author identifier</span>
                </div>

                <div>
                  <label className="block text-xs font-bold text-gray-700 mb-1">
                    IEEE Author ID
                  </label>
                  <input
                    type="text"
                    value={onboardingInputs.ieee}
                    onChange={(e) => setOnboardingInputs({ ...onboardingInputs, ieee: e.target.value })}
                    placeholder="e.g. 37085445363"
                    className="w-full px-3.5 py-2.5 bg-white border border-gray-300 rounded-xl text-xs font-mono focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
                  />
                  <span className="text-[10px] text-gray-400 mt-0.5 block">IEEE Xplore Author identifier</span>
                </div>

                <div>
                  <label className="block text-xs font-bold text-gray-700 mb-1">
                    OpenAlex Author ID
                  </label>
                  <input
                    type="text"
                    value={onboardingInputs.openalex}
                    onChange={(e) => setOnboardingInputs({ ...onboardingInputs, openalex: e.target.value })}
                    placeholder="e.g. A5003901187"
                    className="w-full px-3.5 py-2.5 bg-white border border-gray-300 rounded-xl text-xs font-mono focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
                  />
                  <span className="text-[10px] text-gray-400 mt-0.5 block">OpenAlex open scholarly identifier</span>
                </div>

                <div>
                  <label className="block text-xs font-bold text-gray-700 mb-1">
                    ORCID
                  </label>
                  <input
                    type="text"
                    value={onboardingInputs.orcid}
                    onChange={(e) => setOnboardingInputs({ ...onboardingInputs, orcid: e.target.value })}
                    placeholder="e.g. 0000-0002-1825-0097"
                    className="w-full px-3.5 py-2.5 bg-white border border-gray-300 rounded-xl text-xs font-mono focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
                  />
                  <span className="text-[10px] text-gray-400 mt-0.5 block">16-character ORCID iD</span>
                </div>

                <div>
                  <label className="block text-xs font-bold text-gray-700 mb-1">
                    Semantic Scholar Author ID (Optional)
                  </label>
                  <input
                    type="text"
                    value={onboardingInputs.semantic_scholar}
                    onChange={(e) => setOnboardingInputs({ ...onboardingInputs, semantic_scholar: e.target.value })}
                    placeholder="e.g. 2108194488"
                    className="w-full px-3.5 py-2.5 bg-white border border-gray-300 rounded-xl text-xs font-mono focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold text-gray-700 mb-1">
                    VIDWAN / INFLIBNET ID (Optional)
                  </label>
                  <input
                    type="text"
                    value={onboardingInputs.vidwan}
                    onChange={(e) => setOnboardingInputs({ ...onboardingInputs, vidwan: e.target.value })}
                    placeholder="e.g. 84197"
                    className="w-full px-3.5 py-2.5 bg-white border border-gray-300 rounded-xl text-xs font-mono focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
                  />
                </div>
              </div>

              <div className="pt-2 flex items-center gap-3">
                <button
                  type="submit"
                  disabled={saving}
                  className="px-6 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs rounded-xl shadow-md transition-all cursor-pointer disabled:opacity-50"
                >
                  {saving ? 'Verifying & Saving...' : 'Save & Verify Identifiers'}
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : (
        /* RETURNING FACULTY EXPERIENCE: Manage External Digital Identifiers */
        <div className="stat-card p-8 bg-white border border-gray-200 rounded-3xl shadow-sm">
          <div className="flex flex-col sm:flex-row justify-between sm:items-center gap-2 mb-6">
            <div>
              <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
                <Database className="w-5 h-5 text-indigo-600" />
                External Digital Identifiers
              </h2>
              <p className="text-xs text-gray-500 mt-0.5">
                Permanently associated researcher identities powering automated multi-source discovery.
              </p>
            </div>
            <span className="text-[11px] font-bold text-gray-500 bg-gray-100 px-3 py-1 rounded-full w-fit">
              {identifiersData?.connected_count} of {identifiersData?.total_supported} Sources Connected
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {identifiersData?.identifiers.map((ident) => (
              <div
                key={ident.type}
                className={`p-5 rounded-2xl border transition-all ${
                  ident.is_connected
                    ? 'bg-slate-50/70 border-gray-200/90 shadow-sm'
                    : 'bg-white border-dashed border-gray-200 hover:border-indigo-300'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-extrabold text-gray-800 tracking-wide uppercase">
                    {ident.name}
                  </span>
                  {ident.is_connected ? (
                    ident.verified ? (
                      <span className="flex items-center gap-1 text-[10px] font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2.5 py-0.5 rounded-full">
                        <CheckCircle2 className="w-3 h-3 text-emerald-600" /> Identity: VERIFIED
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 text-[10px] font-bold text-amber-700 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-full">
                        <AlertCircle className="w-3 h-3 text-amber-600" /> Identity: AMBIGUOUS
                      </span>
                    )
                  ) : ident.type === 'openalex' ? (
                    <span className="text-[10px] font-bold text-rose-700 bg-rose-50 border border-rose-200 px-2 py-0.5 rounded-full">
                      Mismatched identifier — rejected
                    </span>
                  ) : (
                    <span className="text-[10px] font-semibold text-gray-400 bg-gray-50 px-2 py-0.5 rounded-full">
                      Not Connected
                    </span>
                  )}
                </div>

                {editingType === ident.type ? (
                  /* Inline Edit Form */
                  <div className="space-y-2 mt-3">
                    <input
                      type="text"
                      value={inputValue}
                      onChange={(e) => setInputValue(e.target.value)}
                      placeholder={ident.placeholder || 'Enter identifier'}
                      className="w-full px-3 py-2 bg-white border border-indigo-400 rounded-lg text-xs font-mono focus:ring-2 focus:ring-indigo-500 outline-none"
                    />
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleSaveSingleIdentifier(ident.type)}
                        disabled={saving}
                        className="px-3 py-1 bg-indigo-600 text-white font-bold text-[11px] rounded-lg hover:bg-indigo-700"
                      >
                        Save
                      </button>
                      <button
                        onClick={() => {
                          setEditingType(null);
                          setInputValue('');
                        }}
                        className="px-3 py-1 bg-gray-200 text-gray-700 font-bold text-[11px] rounded-lg hover:bg-gray-300"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : ident.is_connected ? (
                  /* Connected State */
                  <div className="space-y-2.5 mt-2">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs font-bold text-gray-900 bg-white px-2.5 py-1 border border-gray-200 rounded-lg">
                        {ident.value}
                      </span>
                      {ident.profile_url && (
                        <a
                          href={ident.profile_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-indigo-600 hover:text-indigo-800 text-[11px] font-semibold flex items-center gap-1"
                        >
                          Profile <ExternalLink className="w-3 h-3" />
                        </a>
                      )}
                    </div>

                    <div className="flex flex-wrap gap-1.5 text-[10px]">
                      <span className={`px-2 py-0.5 rounded font-mono font-medium ${
                        ident.live_api_status === 'CONFIGURED'
                          ? 'bg-blue-50 text-blue-700 border border-blue-200'
                          : 'bg-amber-50 text-amber-700 border border-amber-200'
                      }`}>
                        Live API: {ident.live_api_status || 'NOT_CONFIGURED'}
                      </span>
                      <span className="px-2 py-0.5 rounded font-mono font-medium bg-slate-100 text-slate-700 border border-slate-200">
                        Ingestion: {ident.ingestion_status || 'NOT_CONFIGURED'}
                      </span>
                    </div>

                    <div className="flex items-center justify-between pt-2 border-t border-gray-200/60 text-[11px]">
                      <span className="text-gray-400">
                        {ident.last_verified_at ? `Verified: ${new Date(ident.last_verified_at).toLocaleDateString()}` : 'Connected'}
                      </span>
                      <div className="flex items-center gap-1.5">
                        <button
                          onClick={() => handleReverify(ident.type)}
                          disabled={saving}
                          title="Verify Again"
                          className="p-1 text-gray-500 hover:text-indigo-600 rounded hover:bg-indigo-50 cursor-pointer"
                        >
                          <RefreshCw className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => {
                            setEditingType(ident.type);
                            setInputValue(ident.value || '');
                          }}
                          title="Edit Identifier"
                          className="p-1 text-gray-500 hover:text-indigo-600 rounded hover:bg-indigo-50 cursor-pointer"
                        >
                          <Edit3 className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => handleDeleteIdentifier(ident.type)}
                          disabled={saving}
                          title="Remove Identifier"
                          className="p-1 text-gray-400 hover:text-rose-600 rounded hover:bg-rose-50 cursor-pointer"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  </div>
                ) : (
                  /* Unconnected State */
                  <div className="mt-3">
                    <p className="text-[11px] text-gray-400 mb-3">{ident.description}</p>
                    <button
                      onClick={() => {
                        setEditingType(ident.type);
                        setInputValue('');
                      }}
                      className="w-full flex items-center justify-center gap-1.5 py-1.5 bg-gray-50 hover:bg-indigo-50 text-gray-700 hover:text-indigo-700 border border-gray-200 hover:border-indigo-200 rounded-xl text-xs font-bold transition-all cursor-pointer"
                    >
                      <Plus className="w-3.5 h-3.5" /> Connect ID
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* SECTION C & D: RESEARCH METRICS & CONTRIBUTING SOURCES                     */}
      {/* ========================================================================= */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Research Metrics */}
        <div className="lg:col-span-2 stat-card p-6 bg-white border border-gray-200 rounded-3xl shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-bold text-base text-gray-900 flex items-center gap-2">
              <Award className="w-5 h-5 text-indigo-600" />
              Verified Research & Citation Metrics
            </h3>
            <span className="text-[10px] font-semibold text-gray-400">
              Calculated exclusively from confirmed publications
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-2">
            <div className="p-4 bg-slate-50 border border-slate-100 rounded-2xl text-center">
              <p className="text-[11px] font-bold text-gray-500 uppercase tracking-wider">Publications</p>
              <p className="text-2xl font-black text-gray-900 mt-1">
                {latestMetrics.total_publications ?? profile.confirmed_publications_count ?? 0}
              </p>
            </div>
            <div className="p-4 bg-slate-50 border border-slate-100 rounded-2xl text-center">
              <p className="text-[11px] font-bold text-gray-500 uppercase tracking-wider">Total Citations</p>
              <p className="text-2xl font-black text-indigo-600 mt-1">
                {latestMetrics.total_citations ?? 0}
              </p>
            </div>
            <div className="p-4 bg-slate-50 border border-slate-100 rounded-2xl text-center">
              <p className="text-[11px] font-bold text-gray-500 uppercase tracking-wider">h-index</p>
              <p className="text-2xl font-black text-emerald-600 mt-1">
                {latestMetrics.h_index ?? 0}
              </p>
            </div>
            <div className="p-4 bg-slate-50 border border-slate-100 rounded-2xl text-center">
              <p className="text-[11px] font-bold text-gray-500 uppercase tracking-wider">i10-index</p>
              <p className="text-2xl font-black text-amber-600 mt-1">
                {latestMetrics.i10_index ?? 0}
              </p>
            </div>
          </div>
        </div>

        {/* Contributing Scholarly Sources */}
        <div className="stat-card p-6 bg-white border border-gray-200 rounded-3xl shadow-sm">
          <h3 className="font-bold text-base text-gray-900 mb-3 flex items-center gap-2">
            <Layers className="w-5 h-5 text-indigo-600" />
            Contributing Sources
          </h3>
          <p className="text-xs text-gray-500 mb-4">
            Scholarly feeds currently contributing deduplicated records to this profile:
          </p>
          <div className="flex flex-wrap gap-2">
            {profile.contributing_sources && profile.contributing_sources.length > 0 ? (
              profile.contributing_sources.map((src: string) => (
                <span
                  key={src}
                  className="px-3 py-1 bg-indigo-50 text-indigo-800 border border-indigo-200 text-xs font-bold rounded-lg uppercase tracking-wide"
                >
                  {src}
                </span>
              ))
            ) : (
              <span className="text-xs text-gray-400">No active sources linked.</span>
            )}
          </div>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* SECTION E: RESEARCH AREAS                                                 */}
      {/* ========================================================================= */}
      {profile.research_interests && profile.research_interests.length > 0 && (
        <div className="stat-card p-6 bg-white border border-gray-200 rounded-3xl shadow-sm">
          <h3 className="font-bold text-base text-gray-900 mb-3 flex items-center gap-2">
            <Search className="w-5 h-5 text-indigo-600" />
            Research Areas & Specializations
          </h3>
          <div className="flex flex-wrap gap-2">
            {profile.research_interests.map((area: string, idx: number) => (
              <span
                key={idx}
                className="px-3 py-1.5 bg-slate-100 text-slate-700 text-xs font-medium rounded-xl border border-slate-200"
              >
                {area}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* SECTION F: CONFIRMED PUBLICATIONS PREVIEW                                 */}
      {/* ========================================================================= */}
      <div className="stat-card p-8 bg-white border border-gray-200 rounded-3xl shadow-sm">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="font-bold text-lg text-gray-900 flex items-center gap-2">
              <BookOpen className="w-5 h-5 text-indigo-600" />
              Confirmed Publications ({profile.confirmed_publications_count ?? 0})
            </h3>
            <p className="text-xs text-gray-500 mt-0.5">
              Verified publications contributing directly to institutional ranking and personal metrics.
            </p>
          </div>
          <a
            href="/my-publications"
            className="text-xs font-bold text-indigo-600 hover:text-indigo-800 flex items-center gap-1"
          >
            View All in My Publications →
          </a>
        </div>

        {profile.recent_publications && profile.recent_publications.length > 0 ? (
          <div className="divide-y divide-gray-100">
            {profile.recent_publications.map((pub: any) => {
              const pubUrl = pub.doi
                ? `https://doi.org/${pub.doi}`
                : pub.sources?.[0]?.url || null;

              return (
                <div key={pub.id} className="py-4 first:pt-0 last:pb-0">
                  <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-2">
                    <div className="space-y-1">
                      {pubUrl ? (
                        <a
                          href={pubUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="font-bold text-sm text-indigo-900 hover:text-indigo-600 leading-snug flex items-center gap-1.5"
                        >
                          {pub.title} <ExternalLink className="w-3.5 h-3.5 opacity-60 shrink-0" />
                        </a>
                      ) : (
                        <h4 className="font-bold text-sm text-gray-900 leading-snug">{pub.title}</h4>
                      )}
                      <p className="text-xs text-gray-500">{pub.authors_raw}</p>
                      <div className="flex flex-wrap items-center gap-2 text-[11px] text-gray-400 mt-1">
                        {pub.venue && <span>{pub.venue}</span>}
                        {pub.year && <span className="font-semibold text-gray-700">({pub.year})</span>}
                        {pub.doi && <span className="font-mono text-gray-500">DOI: {pub.doi}</span>}
                      </div>
                    </div>

                    <div className="flex sm:flex-col items-center sm:items-end gap-2 shrink-0">
                      <span className="px-2.5 py-1 bg-indigo-50 border border-indigo-100 text-indigo-800 text-xs font-extrabold rounded-lg">
                        {pub.citation_count} citations
                      </span>
                      <div className="flex gap-1">
                        {pub.sources?.map((s: any, sIdx: number) => (
                          <span
                            key={sIdx}
                            className="px-1.5 py-0.5 bg-gray-100 text-gray-600 text-[9px] font-bold rounded uppercase"
                          >
                            {s.system}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="text-center py-8 text-gray-400 text-xs">
            No confirmed publications found yet. Connect your researcher identifiers above to synchronize your research records.
          </div>
        )}
      </div>
    </div>
  );
}
