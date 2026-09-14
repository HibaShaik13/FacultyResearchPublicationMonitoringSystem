import { useState } from 'react';
import api from '../services/api';
import { Search, BookOpen } from 'lucide-react';

export default function ResearchSearch() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<any[]>([]);
  const [searched, setSearched] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setSearched(true);
    try {
      const res = await api.get(`/api/v1/publications/?search=${encodeURIComponent(query.trim())}`);
      setResults(res.data.data || []);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 max-w-4xl mx-auto pb-12">
      <div className="bg-white/90 backdrop-blur-md p-8 text-center rounded-2xl border border-gray-200/80 shadow-sm mt-4">
        <div className="w-12 h-12 bg-indigo-50 text-indigo-600 rounded-2xl flex items-center justify-center mx-auto mb-3">
          <BookOpen className="w-6 h-6" />
        </div>
        <h2 className="text-2xl font-bold text-gray-900 mb-1">Global Scholarly Search</h2>
        <p className="text-xs text-gray-500 mb-6">Search across verified publications, faculty co-authors, DOIs, and venues in real time.</p>
        <form onSubmit={handleSearch} className="relative max-w-xl mx-auto">
          <Search className="absolute left-4 top-3.5 text-gray-400 w-5 h-5" />
          <input 
            type="text" 
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by publication title, keywords, or DOI..." 
            className="w-full pl-12 pr-28 py-3 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 outline-none text-gray-900 transition-all shadow-inner" 
          />
          <button
            type="submit"
            disabled={loading}
            className="absolute right-2 top-2 px-4 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-lg transition disabled:opacity-50"
          >
            {loading ? 'Searching...' : 'Search'}
          </button>
        </form>
      </div>

      {loading && (
        <div className="p-8 text-center text-gray-400 text-sm">
          Querying verified institutional database...
        </div>
      )}

      {!loading && searched && results.length === 0 && (
        <div className="bg-white/90 p-8 text-center rounded-2xl border border-gray-200/80 shadow-sm text-gray-500 text-sm">
          No research records found matching "{query}". Try a different keyword or DOI.
        </div>
      )}

      {!loading && results.length > 0 && (
        <div className="bg-white/90 backdrop-blur-md p-6 rounded-2xl border border-gray-200/80 shadow-sm space-y-4">
          <div className="flex items-center justify-between border-b border-gray-100 pb-3">
            <h3 className="font-bold text-gray-900 text-base">Search Results ({results.length})</h3>
            <span className="text-xs text-gray-400 font-medium">Verified Database Matches</span>
          </div>
          <div className="divide-y divide-gray-100">
            {results.map(r => (
              <div key={r.id} className="py-4 space-y-1.5 hover:bg-gray-50/50 p-3 rounded-xl transition">
                <div className="flex items-start justify-between gap-3">
                  <h4 className="font-bold text-indigo-700 text-sm leading-snug">{r.title}</h4>
                  <span className={`px-2 py-0.5 rounded text-[11px] font-semibold shrink-0 ${
                    (r.verification_status || '').includes('verified')
                      ? 'bg-emerald-100 text-emerald-700 border border-emerald-200'
                      : 'bg-amber-100 text-amber-700 border border-amber-200'
                  }`}>
                    {r.verification_status || 'unverified'}
                  </span>
                </div>
                <p className="text-xs text-gray-600 font-medium">
                  {r.authors && r.authors.length > 0
                    ? r.authors.map((a: any) => a.name).filter(Boolean).join(', ')
                    : 'Faculty Co-Authors'}
                </p>
                <div className="flex flex-wrap items-center gap-3 text-[11px] text-gray-500 pt-1">
                  <span>{r.journal_name || r.conference_name || 'Academic Venue'}</span>
                  {r.year && <span>• Year: {r.year}</span>}
                  {r.doi && <span className="font-mono text-gray-400">• DOI: {r.doi}</span>}
                  {r.citation_count !== undefined && <span>• Citations: {r.citation_count}</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
