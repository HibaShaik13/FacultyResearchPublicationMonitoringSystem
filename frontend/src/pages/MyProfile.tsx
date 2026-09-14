import { useEffect, useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import api from '../services/api';

export default function MyProfile() {
  const { user } = useAuth();
  const [profile, setProfile] = useState<any>(null);

  useEffect(() => {
    if (user?.role === 'faculty' && user?.faculty_id) {
      api.get(`/api/v1/faculty/${user.faculty_id}`).then(res => setProfile(res.data));
    } else if (user?.role === 'admin' || user?.role === 'research_admin') {
      // Admin doesn't have a specific profile here, or we can handle it differently.
      setProfile({ admin: true });
    }
  }, [user]);

  if (profile?.admin) {
    return (
      <div className="space-y-6">
        <div className="stat-card p-8 bg-white/90 border border-gray-200/80 rounded-2xl shadow-sm">
          <h2 className="text-2xl font-bold text-gray-900 mb-2">Institutional Administrator Profile</h2>
          <p className="text-indigo-600 font-semibold text-sm">Role: {user?.role?.toUpperCase()} • {user?.email}</p>
          <p className="text-gray-500 text-xs mt-2">
            As an institutional administrator, your account possesses cross-departmental administrative authority, full verification queue review privileges, and global reporting capabilities.
          </p>
        </div>
      </div>
    );
  }

  if (!profile) return <div className="p-8 text-center text-gray-400">Loading profile details from database...</div>;

  return (
    <div className="space-y-6">
      <div className="stat-card p-8 bg-white/90 border border-gray-200/80 rounded-2xl shadow-sm">
        <h2 className="text-2xl font-bold mb-1 text-gray-900">
          {profile.title_prefix || 'Dr.'} {profile.first_name} {profile.last_name || profile.raw_name}
        </h2>
        <p className="text-indigo-600 font-semibold text-sm">{profile.designation} • Department of {profile.department}</p>
        <p className="text-gray-500 text-xs mt-1.5">{profile.institutional_email || profile.raw_email}</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="stat-card p-6 bg-white/90 border border-gray-200/80 rounded-2xl shadow-sm">
          <h3 className="font-bold text-base mb-4 text-gray-800">External Digital Identifiers</h3>
          {profile.identifiers && profile.identifiers.length > 0 ? (
            <ul className="space-y-2.5">
              {profile.identifiers.map((id: any) => (
                <li key={id.type} className="flex justify-between p-3 bg-gray-50 border border-gray-100 rounded-xl items-center text-xs">
                  <span className="font-semibold text-gray-700">{id.type}</span>
                  <span className="font-mono text-gray-600">{id.value}</span>
                  {id.verified && <span className="text-emerald-700 text-[10px] font-bold border border-emerald-200 bg-emerald-50 px-2 py-0.5 rounded-full">Verified</span>}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-gray-400">No external identifier overrides registered.</p>
          )}
        </div>
        
        <div className="stat-card p-6 bg-white/90 border border-gray-200/80 rounded-2xl shadow-sm">
          <h3 className="font-bold text-base mb-4 text-gray-800">Research & Citation Metrics</h3>
          {profile.metric_snapshots && profile.metric_snapshots.length > 0 ? (
            <div className="space-y-3 mt-2 text-xs">
               <div className="flex justify-between pb-2 border-b border-gray-100">
                 <span className="text-gray-500 font-medium">Total Citations</span>
                 <span className="text-gray-900 font-bold text-sm">{profile.metric_snapshots[0].total_citations}</span>
               </div>
               <div className="flex justify-between pb-2 border-b border-gray-100">
                 <span className="text-gray-500 font-medium">h-index</span>
                 <span className="text-gray-900 font-bold text-sm">{profile.metric_snapshots[0].h_index}</span>
               </div>
               <div className="flex justify-between">
                 <span className="text-gray-500 font-medium">i10-index</span>
                 <span className="text-gray-900 font-bold text-sm">{profile.metric_snapshots[0].i10_index}</span>
               </div>
            </div>
          ) : <p className="text-xs text-gray-400">Standard citation snapshots synchronized with OpenAlex.</p>}
        </div>
      </div>
    </div>
  );
}
