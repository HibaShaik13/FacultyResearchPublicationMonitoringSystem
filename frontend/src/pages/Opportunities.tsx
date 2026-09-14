import { useEffect, useState } from 'react';
import api from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { 
  Sparkles, 
  Calendar, 
  DollarSign, 
  Building, 
  ArrowUpRight,
  Search
} from 'lucide-react';

interface ResearchOpportunity {
  id: string;
  title: string;
  agency: string;
  grant_amount: string;
  deadline: string;
  type: string;
  eligible_departments: string[];
  matching_domains: string[];
  description: string;
  url: string;
  relevance_score: number;
  matched_tags: string[];
}

export default function Opportunities() {
  const { user } = useAuth();
  const [opportunities, setOpportunities] = useState<ResearchOpportunity[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedType, setSelectedType] = useState('all');

  useEffect(() => {
    fetchOpportunities();
  }, [user]);

  const fetchOpportunities = async () => {
    setLoading(true);
    try {
      const facParam = user?.faculty_id ? `?faculty_id=${user.faculty_id}` : '';
      const res = await api.get(`/api/v1/analytics/opportunities${facParam}`);
      setOpportunities(res.data || []);
    } catch (err) {
      console.error('Failed to load opportunities:', err);
    } finally {
      setLoading(false);
    }
  };

  const filteredOpps = opportunities.filter(opp => {
    const matchesType = selectedType === 'all' || opp.type.toLowerCase().includes(selectedType.toLowerCase());
    if (!matchesType) return false;
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      opp.title.toLowerCase().includes(q) ||
      opp.agency.toLowerCase().includes(q) ||
      opp.description.toLowerCase().includes(q) ||
      opp.matched_tags.some(t => t.toLowerCase().includes(q))
    );
  });

  return (
    <div className="space-y-6 max-w-6xl mx-auto pb-12">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white/90 backdrop-blur-md p-6 rounded-2xl border border-gray-200/80 shadow-sm">
        <div>
          <div className="flex items-center gap-2">
            <div className="p-2 bg-emerald-50 text-emerald-700 rounded-lg border border-emerald-100">
              <Sparkles size={24} />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Research & Funding Opportunities</h1>
              <p className="text-sm text-gray-500 mt-0.5">
                Targeted national grants, call-for-papers, and innovation schemes matched to verified faculty expertise.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchOpportunities}
            className="px-4 py-2 text-xs font-semibold bg-white border border-gray-200 text-gray-700 hover:bg-gray-50 rounded-xl shadow-sm transition-colors"
          >
            Refresh Calls
          </button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center justify-between">
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0 custom-scrollbar">
          {[
            { id: 'all', label: 'All Opportunities' },
            { id: 'grant', label: 'Govt Grants' },
            { id: 'scheme', label: 'National Schemes' },
            { id: 'conference', label: 'Conferences & Venues' },
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setSelectedType(tab.id)}
              className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-all ${
                selectedType === tab.id
                  ? 'bg-emerald-600 text-white shadow-sm'
                  : 'bg-white/80 text-gray-600 hover:bg-white hover:text-gray-900 border border-gray-200'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="relative w-full sm:w-64">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={16} />
          <input
            type="text"
            placeholder="Search grants, agencies, domains..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-4 py-1.5 text-xs bg-white border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-100 focus:border-emerald-400 shadow-sm"
          />
        </div>
      </div>

      {/* Opportunities List */}
      <div className="space-y-4">
        {loading ? (
          <div className="p-12 text-center text-gray-400 bg-white/80 rounded-2xl border border-gray-200">
            Matching grant opportunities to faculty domain profiles...
          </div>
        ) : filteredOpps.length === 0 ? (
          <div className="p-12 text-center text-gray-400 bg-white/80 rounded-2xl border border-gray-200">
            No opportunities currently match the selected filter.
          </div>
        ) : (
          filteredOpps.map(opp => (
            <div
              key={opp.id}
              className="bg-white/95 backdrop-blur-md p-6 rounded-2xl border border-gray-200/80 shadow-sm hover:border-emerald-300 hover:shadow-md transition-all"
            >
              <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4">
                <div className="space-y-3 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs font-bold px-2.5 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-200">
                      {opp.type}
                    </span>
                    <span className="text-xs font-semibold text-gray-500 flex items-center gap-1">
                      <Building size={13} /> {opp.agency}
                    </span>
                    <span className="ml-auto inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-blue-50 text-blue-700 border border-blue-200">
                      <Sparkles size={12} /> {opp.relevance_score}% Match
                    </span>
                  </div>

                  <h3 className="text-lg font-bold text-gray-900 leading-snug">{opp.title}</h3>
                  <p className="text-sm text-gray-600 leading-relaxed">{opp.description}</p>

                  <div className="flex flex-wrap items-center gap-4 text-xs font-semibold text-gray-700 pt-1">
                    <span className="flex items-center gap-1.5 text-emerald-700 bg-emerald-50 px-3 py-1 rounded-lg border border-emerald-100">
                      <DollarSign size={14} /> {opp.grant_amount}
                    </span>
                    <span className="flex items-center gap-1.5 text-amber-700 bg-amber-50 px-3 py-1 rounded-lg border border-amber-100">
                      <Calendar size={14} /> Deadline: {opp.deadline}
                    </span>
                    <span className="text-gray-500">
                      Departments: {opp.eligible_departments.join(', ')}
                    </span>
                  </div>

                  {opp.matched_tags && opp.matched_tags.length > 0 && (
                    <div className="flex flex-wrap items-center gap-1.5 pt-2">
                      <span className="text-[11px] font-bold text-gray-400 mr-1">Matching Expertise:</span>
                      {opp.matched_tags.map((tag, idx) => (
                        <span
                          key={idx}
                          className="text-[11px] font-medium px-2.5 py-0.5 rounded-md bg-gray-100 text-gray-700 border border-gray-200"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                <div className="lg:pl-6 lg:border-l border-gray-100 flex lg:flex-col items-center justify-between gap-3 shrink-0">
                  <a
                    href={opp.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="w-full px-4 py-2.5 text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 rounded-xl shadow-sm transition-colors flex items-center justify-center gap-1.5"
                  >
                    <span>Official Portal</span>
                    <ArrowUpRight size={14} />
                  </a>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
