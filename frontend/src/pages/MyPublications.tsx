import { useEffect, useState } from 'react';
import api from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { Search, ExternalLink } from 'lucide-react';

export function getPublicationUrl(pub: { doi?: string | null; source_url?: string | null }): string | null {
  if (pub.doi && pub.doi.trim()) {
    const cleanDoi = pub.doi.trim();
    if (cleanDoi.startsWith('http://') || cleanDoi.startsWith('https://')) {
      return cleanDoi;
    }
    return `https://doi.org/${cleanDoi}`;
  }
  if (pub.source_url && pub.source_url.trim()) {
    return pub.source_url.trim();
  }
  return null;
}

export default function MyPublications() {
  const [pubs, setPubs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');

  const { user } = useAuth();

  useEffect(() => {
    setLoading(true);
    const url = user?.role === 'faculty' && user.faculty_id
      ? `/api/v1/publications/?faculty_id=${user.faculty_id}`
      : '/api/v1/publications/';
    api.get(url)
      .then(res => setPubs(res.data.data || []))
      .catch(() => setPubs([]))
      .finally(() => setLoading(false));
  }, [user]);

  const filteredPubs = pubs.filter(p =>
    (p.title || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
    (p.doi || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
    (p.journal_name || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
    (p.conference_name || '').toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <div className="stat-card flex flex-col sm:flex-row justify-between sm:items-center gap-4 mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">
            {user?.role === 'faculty' ? 'My Publications' : 'All Institutional Publications'}
          </h2>
          <p className="text-xs text-gray-500 mt-0.5">
            {filteredPubs.length} verified and discovered research works
          </p>
        </div>
        <div className="relative">
          <Search className="absolute left-3 top-2.5 text-gray-400 w-4 h-4" />
          <input
            type="text"
            placeholder="Search DOI, title, venue..."
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
            className="pl-9 pr-4 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm focus:border-blue-500 outline-none text-gray-900 focus:ring-2 focus:ring-blue-100 transition-all shadow-inner w-full sm:w-64"
          />
        </div>
      </div>

      <div className="stat-card overflow-hidden p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="p-4 font-semibold text-gray-600">Title</th>
                <th className="p-4 font-semibold text-gray-600">Year</th>
                <th className="p-4 font-semibold text-gray-600">Venue</th>
                <th className="p-4 font-semibold text-gray-600">Citations</th>
                <th className="p-4 font-semibold text-gray-600">Verification</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={5} className="p-8 text-center text-gray-400">
                    Loading publications from database...
                  </td>
                </tr>
              ) : filteredPubs.length === 0 ? (
                <tr>
                  <td colSpan={5} className="p-8 text-center text-gray-400">
                    No publications found matching your criteria.
                  </td>
                </tr>
              ) : (
                filteredPubs.map(p => {
                  const pubUrl = getPublicationUrl(p);
                  const doiUrl = p.doi ? (p.doi.startsWith('http') ? p.doi : `https://doi.org/${p.doi.trim()}`) : null;

                  return (
                    <tr key={p.id} className="border-b border-gray-100 hover:bg-gray-50 transition-colors">
                      <td className="p-4 max-w-md">
                        {pubUrl ? (
                          <a
                            href={pubUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="font-medium text-blue-700 hover:text-blue-900 hover:underline inline-flex items-center gap-1.5 group transition-colors leading-snug"
                            title="Open publication in new tab"
                          >
                            <span>{p.title}</span>
                            <ExternalLink size={13} className="shrink-0 text-blue-500 group-hover:text-blue-700 transition-transform group-hover:translate-x-0.5" />
                          </a>
                        ) : (
                          <div className="font-medium text-gray-800 leading-snug" title={p.title}>
                            {p.title}
                          </div>
                        )}

                        {doiUrl ? (
                          <div className="flex items-center gap-1 text-[11px] font-mono text-gray-500 mt-1">
                            <span>DOI:</span>
                            <a
                              href={doiUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-blue-600 hover:underline hover:text-blue-800 inline-flex items-center gap-0.5"
                            >
                              <span>{p.doi}</span>
                              <ExternalLink size={10} className="shrink-0" />
                            </a>
                          </div>
                        ) : p.source_url ? (
                          <div className="flex items-center gap-1 text-[11px] text-gray-500 mt-1">
                            <a
                              href={p.source_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-blue-600 hover:underline hover:text-blue-800 inline-flex items-center gap-0.5 font-medium"
                            >
                              <span>Source</span>
                              <ExternalLink size={10} className="shrink-0" />
                            </a>
                          </div>
                        ) : (
                          <div className="text-[11px] text-gray-400 italic mt-0.5">
                            Publication link unavailable
                          </div>
                        )}
                      </td>
                      <td className="p-4 text-gray-700">{p.year || 'N/A'}</td>
                      <td className="p-4 text-gray-600 max-w-xs truncate">{p.journal_name || p.conference_name || 'Academic Venue'}</td>
                      <td className="p-4 text-gray-700 font-medium">{p.citation_count || 0}</td>
                      <td className="p-4">
                        <span className={`px-2.5 py-1 rounded text-xs font-semibold ${
                          (p.verification_status || '').includes('verified')
                            ? 'bg-emerald-100 text-emerald-700'
                            : 'bg-amber-100 text-amber-700'
                        }`}>
                          {p.verification_status || 'unverified'}
                        </span>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

