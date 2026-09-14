import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';
import { 
  Search, 
  ArrowRight, 
  Tag, 
  TrendingUp, 
  Users 
} from 'lucide-react';

interface ResearchArea {
  area: string;
  name: string;
  count: number;
  percentage: number;
}

export default function ResearchAreas() {
  const navigate = useNavigate();
  const [areas, setAreas] = useState<ResearchArea[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    fetchResearchAreas();
  }, []);

  const fetchResearchAreas = async () => {
    setLoading(true);
    try {
      const res = await api.get('/api/v1/analytics/research-areas');
      setAreas(res.data.areas || []);
    } catch (err) {
      console.error('Failed to load research areas:', err);
    } finally {
      setLoading(false);
    }
  };

  const filteredAreas = areas.filter(a => {
    if (!searchQuery.trim()) return true;
    return a.area.toLowerCase().includes(searchQuery.toLowerCase());
  });

  const totalInterests = areas.reduce((acc, curr) => acc + curr.count, 0);

  return (
    <div className="space-y-6 max-w-6xl mx-auto pb-12">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white/90 backdrop-blur-md p-6 rounded-2xl border border-gray-200/80 shadow-sm">
        <div>
          <div className="flex items-center gap-2">
            <div className="p-2 bg-blue-50 text-blue-700 rounded-lg border border-blue-100">
              <Tag size={24} />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Research Domains & Topics Explorer</h1>
              <p className="text-sm text-gray-500 mt-0.5">
                Aggregated research focus areas across all institutional faculty profiles and publications.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="relative w-full sm:w-64">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={16} />
            <input
              type="text"
              placeholder="Search research topics..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-4 py-2 text-xs bg-white border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-100 focus:border-blue-400 shadow-sm"
            />
          </div>
        </div>
      </div>

      {/* KPI Overview */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white/90 backdrop-blur-md p-5 rounded-2xl border border-gray-200/80 shadow-sm flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-blue-50 border border-blue-100 flex items-center justify-center text-blue-600 font-bold">
            <Tag size={22} />
          </div>
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Identified Domains</p>
            <p className="text-2xl font-extrabold text-gray-900 mt-0.5">{areas.length}</p>
          </div>
        </div>

        <div className="bg-white/90 backdrop-blur-md p-5 rounded-2xl border border-gray-200/80 shadow-sm flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-emerald-50 border border-emerald-100 flex items-center justify-center text-emerald-600 font-bold">
            <Users size={22} />
          </div>
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Faculty Alignments</p>
            <p className="text-2xl font-extrabold text-gray-900 mt-0.5">{totalInterests}</p>
          </div>
        </div>

        <div className="bg-white/90 backdrop-blur-md p-5 rounded-2xl border border-gray-200/80 shadow-sm flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-purple-50 border border-purple-100 flex items-center justify-center text-purple-600 font-bold">
            <TrendingUp size={22} />
          </div>
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Primary Research Thrust</p>
            <p className="text-base font-bold text-gray-900 mt-0.5 truncate max-w-[200px]">
              {areas.length > 0 ? areas[0].area : 'Machine Learning'}
            </p>
          </div>
        </div>
      </div>

      {/* Grid of Research Areas */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {loading ? (
          <div className="col-span-full p-12 text-center text-gray-400 bg-white/80 rounded-2xl border border-gray-200">
            Analyzing faculty research interests and topic clustering...
          </div>
        ) : filteredAreas.length === 0 ? (
          <div className="col-span-full p-12 text-center text-gray-400 bg-white/80 rounded-2xl border border-gray-200">
            No research domains matching search query.
          </div>
        ) : (
          filteredAreas.map(area => (
            <div
              key={area.area}
              onClick={() => navigate(`/search?q=${encodeURIComponent(area.area)}`)}
              className="bg-white/95 backdrop-blur-md p-5 rounded-2xl border border-gray-200/80 shadow-sm hover:border-blue-400 hover:shadow-md transition-all cursor-pointer group flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between mb-2.5">
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-100">
                    {area.percentage}% Share
                  </span>
                  <span className="text-xs font-semibold text-gray-400 group-hover:text-blue-600 transition-colors flex items-center gap-1">
                    <span>Search</span>
                    <ArrowRight size={13} />
                  </span>
                </div>

                <h3 className="text-base font-bold text-gray-900 group-hover:text-blue-700 transition-colors leading-snug">
                  {area.area}
                </h3>
              </div>

              <div className="mt-4 pt-3 border-t border-gray-100">
                <div className="w-full bg-gray-100 h-1.5 rounded-full overflow-hidden mb-2">
                  <div
                    className="bg-blue-600 h-full rounded-full transition-all duration-500"
                    style={{ width: `${Math.max(8, area.percentage * 3)}%` }}
                  ></div>
                </div>
                <div className="flex items-center justify-between text-xs text-gray-500">
                  <span className="font-medium flex items-center gap-1">
                    <Users size={12} /> {area.count} Faculty Active
                  </span>
                  <span className="text-blue-600 font-semibold group-hover:underline">
                    Explore publications
                  </span>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
