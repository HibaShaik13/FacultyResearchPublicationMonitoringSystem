import { useEffect, useState } from 'react';
import api from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import {
  TrendingUp,
  Award,
  BookOpen,
  FileCheck,
  Building,
  Filter,
  PieChart as PieIcon,
  RefreshCw,
} from 'lucide-react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';

interface TrendItem {
  year: number;
  count?: number;
  publications?: number;
  citations?: number;
}

interface ResearchAreaItem {
  area: string;
  count: number;
  percentage: number;
}

interface FacultyLeaderboardItem {
  id: string;
  name: string;
  department: string;
  designation: string;
  email: string;
  total_publications?: number;
  verified_count?: number;
  h_index?: number;
}

export default function ResearchImpact() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<any>({});
  const [pubTrends, setPubTrends] = useState<TrendItem[]>([]);
  const [citationTrends, setCitationTrends] = useState<TrendItem[]>([]);
  const [researchAreas, setResearchAreas] = useState<ResearchAreaItem[]>([]);
  const [facultyList, setFacultyList] = useState<FacultyLeaderboardItem[]>([]);
  const [timeRange, setTimeRange] = useState<'all' | '5y' | '3y'>('all');

  const isFaculty = user?.role === 'faculty' && Boolean(user?.faculty_id);
  const facultyIdParam = isFaculty ? `?faculty_id=${user.faculty_id}` : '';

  const loadData = async () => {
    setLoading(true);
    try {
      const [dashRes, pubRes, citRes, areaRes, facRes] = await Promise.all([
        api.get(`/api/v1/analytics/dashboard${facultyIdParam}`),
        api.get(`/api/v1/analytics/publication-trends${facultyIdParam}`),
        api.get(`/api/v1/analytics/citation-trends${facultyIdParam}`),
        api.get(`/api/v1/analytics/research-areas${facultyIdParam}`),
        !isFaculty ? api.get('/api/v1/faculty?limit=10') : Promise.resolve({ data: { data: [] } }),
      ]);

      setStats(dashRes.data || {});
      setPubTrends(pubRes.data?.trends || []);
      setCitationTrends(citRes.data?.trends || []);
      setResearchAreas(areaRes.data?.areas || []);
      setFacultyList(facRes.data?.data || []);
    } catch (err) {
      console.error('Failed to load research impact data', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [user]);

  // Combine trends for the unified chart
  const combinedTrends = pubTrends.map((p) => {
    const matchingCit = citationTrends.find((c) => c.year === p.year);
    return {
      year: p.year,
      publications: p.count || p.publications || 0,
      citations: matchingCit?.citations || 0,
    };
  });

  const filteredTrends =
    timeRange === '5y'
      ? combinedTrends.slice(-5)
      : timeRange === '3y'
      ? combinedTrends.slice(-3)
      : combinedTrends;

  return (
    <div className="space-y-6 pb-12 font-sans">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-white p-6 rounded-2xl border border-gray-200/80 shadow-sm">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2.5 py-0.5 rounded-full text-xs font-bold uppercase tracking-wider bg-blue-100 text-blue-800">
              Institutional Intelligence
            </span>
            <span className="text-xs text-gray-500 font-medium">Research Performance & Trajectory</span>
          </div>
          <h1 className="text-2xl font-extrabold text-gray-900 mt-2 flex items-center gap-2">
            <TrendingUp className="text-blue-600" size={28} />
            Research Impact & Citation Analytics
          </h1>
          <p className="text-sm text-gray-600 mt-1">
            {isFaculty
              ? 'Comprehensive view of your scholarly output, citation benchmarks, and publication trajectory.'
              : 'Institutional-level research output growth, citation velocity, and departmental research impact.'}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 bg-gray-50 border border-gray-200 rounded-xl px-3 py-1.5 text-xs font-medium text-gray-700">
            <Filter size={13} className="text-gray-400" />
            <span>Range:</span>
            <select
              value={timeRange}
              onChange={(e: any) => setTimeRange(e.target.value)}
              className="bg-transparent focus:outline-none font-semibold text-blue-700"
            >
              <option value="all">All Available Years</option>
              <option value="5y">Last 5 Years</option>
              <option value="3y">Last 3 Years</option>
            </select>
          </div>

          <button
            onClick={loadData}
            className="px-3.5 py-2 bg-gray-50 hover:bg-gray-100 text-gray-700 border border-gray-200 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-colors"
          >
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} /> Refresh
          </button>
        </div>
      </div>

      {/* KPI Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Publications */}
        <div className="stat-card p-5 bg-white border border-gray-200 rounded-2xl shadow-sm flex items-center justify-between group hover:border-blue-300 transition-all">
          <div>
            <p className="text-xs font-bold text-gray-500 uppercase tracking-wider">Total Publications</p>
            <h3 className="text-3xl font-black text-gray-900 mt-1">{stats.total_publications ?? 0}</h3>
            <p className="text-xs text-emerald-600 font-semibold mt-1 flex items-center gap-1">
              <span className="font-bold">✓ {stats.verified_publications ?? 0}</span> metadata-verified · {Math.max(0, (stats.total_publications || 0) - (stats.verified_publications || 0))} needs review
            </p>
          </div>
          <div className="w-12 h-12 rounded-2xl bg-purple-50 text-purple-600 border border-purple-100 flex items-center justify-center">
            <BookOpen size={24} />
          </div>
        </div>

        {/* Total Citations */}
        <div className="stat-card p-5 bg-white border border-gray-200 rounded-2xl shadow-sm flex items-center justify-between group hover:border-emerald-300 transition-all">
          <div>
            <p className="text-xs font-bold text-gray-500 uppercase tracking-wider">Total Citations</p>
            <h3 className="text-3xl font-black text-gray-900 mt-1">{stats.total_citations ?? 0}</h3>
            <p className="text-xs text-gray-500 font-medium mt-1">Crossref & OpenAlex verified</p>
          </div>
          <div className="w-12 h-12 rounded-2xl bg-emerald-50 text-emerald-600 border border-emerald-100 flex items-center justify-center">
            <TrendingUp size={24} />
          </div>
        </div>

        {/* h-index Benchmark */}
        <div className="stat-card p-5 bg-white border border-gray-200 rounded-2xl shadow-sm flex items-center justify-between group hover:border-blue-300 transition-all">
          <div>
            <p className="text-xs font-bold text-gray-500 uppercase tracking-wider">h-index Benchmark</p>
            <h3 className="text-3xl font-black text-gray-900 mt-1">{stats.h_index ?? 0}</h3>
            <p className="text-xs text-blue-600 font-medium mt-1">Scholarly impact index</p>
          </div>
          <div className="w-12 h-12 rounded-2xl bg-blue-50 text-blue-600 border border-blue-100 flex items-center justify-center">
            <Award size={24} />
          </div>
        </div>

        {/* i10-index Benchmark */}
        <div className="stat-card p-5 bg-white border border-gray-200 rounded-2xl shadow-sm flex items-center justify-between group hover:border-amber-300 transition-all">
          <div>
            <p className="text-xs font-bold text-gray-500 uppercase tracking-wider">i10-index Metric</p>
            <h3 className="text-3xl font-black text-gray-900 mt-1">{stats.i10_index ?? 0}</h3>
            <p className="text-xs text-amber-600 font-medium mt-1">Papers with ≥10 citations</p>
          </div>
          <div className="w-12 h-12 rounded-2xl bg-amber-50 text-amber-600 border border-amber-100 flex items-center justify-center">
            <FileCheck size={24} />
          </div>
        </div>
      </div>

      {/* Main Visualizations Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Publication & Citation Output Over Time */}
        <div className="lg:col-span-2 bg-white p-6 rounded-2xl border border-gray-200 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-bold text-gray-900">Scholarly Output & Growth Trajectory</h3>
              <p className="text-xs text-gray-500">Historical publication volume and citation records by year</p>
            </div>
            <div className="flex items-center gap-3 text-xs">
              <span className="flex items-center gap-1 text-gray-600 font-medium">
                <span className="w-2.5 h-2.5 rounded-full bg-blue-600 inline-block" /> Publications
              </span>
              <span className="flex items-center gap-1 text-gray-600 font-medium">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 inline-block" /> Citations
              </span>
            </div>
          </div>

          <div className="h-80 w-full pt-2">
            {filteredTrends.length === 0 ? (
              <div className="h-full flex items-center justify-center text-gray-400 text-sm">
                No publication trend records available for the selected timeframe.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={filteredTrends} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="pubGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#2563eb" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="#2563eb" stopOpacity={0.0} />
                    </linearGradient>
                    <linearGradient id="citGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#10b981" stopOpacity={0.0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                  <XAxis dataKey="year" stroke="#94a3b8" fontSize={12} tickLine={false} />
                  <YAxis stroke="#94a3b8" fontSize={12} tickLine={false} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#ffffff',
                      border: '1px solid #e2e8f0',
                      borderRadius: '12px',
                      boxShadow: '0 4px 20px rgba(0,0,0,0.08)',
                      fontSize: '12px',
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="publications"
                    name="Publications"
                    stroke="#2563eb"
                    strokeWidth={2.5}
                    fillOpacity={1}
                    fill="url(#pubGrad)"
                  />
                  <Area
                    type="monotone"
                    dataKey="citations"
                    name="Citations"
                    stroke="#10b981"
                    strokeWidth={2}
                    fillOpacity={1}
                    fill="url(#citGrad)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* Right Col: Top Research Fields / Specializations */}
        <div className="bg-white p-6 rounded-2xl border border-gray-200 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-bold text-gray-900 flex items-center gap-2">
              <PieIcon className="text-blue-600" size={18} />
              Research Focus Areas
            </h3>
            <span className="text-xs text-gray-400 font-medium">{researchAreas.length} Fields</span>
          </div>

          <p className="text-xs text-gray-500">
            Real keyword distribution derived from faculty expertise and published works
          </p>

          <div className="space-y-3 pt-2">
            {researchAreas.length === 0 ? (
              <div className="text-center py-10 text-gray-400 text-xs italic">
                No research area classifications indexed.
              </div>
            ) : (
              researchAreas.map((item, idx) => (
                <div key={idx} className="space-y-1">
                  <div className="flex justify-between text-xs font-semibold">
                    <span className="text-gray-800 truncate pr-2">{item.area}</span>
                    <span className="text-blue-600 shrink-0">{item.percentage}%</span>
                  </div>
                  <div className="w-full bg-gray-100 h-2 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${
                        idx === 0
                          ? 'bg-blue-600'
                          : idx === 1
                          ? 'bg-indigo-500'
                          : idx === 2
                          ? 'bg-sky-500'
                          : idx === 3
                          ? 'bg-emerald-500'
                          : 'bg-amber-500'
                      }`}
                      style={{ width: `${Math.max(5, item.percentage)}%` }}
                    />
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Faculty Research Impact Leaders (for Admin view) */}
      {!isFaculty && facultyList.length > 0 && (
        <div className="bg-white p-6 rounded-2xl border border-gray-200 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-bold text-gray-900 flex items-center gap-2">
                <Building className="text-blue-600" size={18} />
                Faculty Research Contributors
              </h3>
              <p className="text-xs text-gray-500">
                Authoritative researcher index with verified publication volume and institutional department
              </p>
            </div>
            <span className="text-xs font-bold text-blue-700 bg-blue-50 px-3 py-1 rounded-full border border-blue-200">
              {facultyList.length} Active Researchers
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-gray-200 text-gray-500 font-bold uppercase text-[11px] tracking-wider">
                  <th className="py-3 px-4">Researcher Name</th>
                  <th className="py-3 px-4">Department</th>
                  <th className="py-3 px-4">Designation</th>
                  <th className="py-3 px-4">Email</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 text-gray-700">
                {facultyList.map((fac, idx) => (
                  <tr key={fac.id || idx} className="hover:bg-gray-50/80 transition-colors">
                    <td className="py-3 px-4 font-bold text-gray-900 flex items-center gap-2">
                      <div className="w-7 h-7 rounded-full bg-blue-100 text-blue-800 flex items-center justify-center font-black text-xs">
                        {fac.name.charAt(0)}
                      </div>
                      <span>{fac.name}</span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="bg-blue-50 text-blue-700 font-semibold px-2 py-0.5 rounded border border-blue-200">
                        {fac.department || 'CSE'}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-gray-600">{fac.designation || 'Faculty'}</td>
                    <td className="py-3 px-4 font-mono text-gray-500">{fac.email}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
