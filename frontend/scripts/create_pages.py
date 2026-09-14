import os

pages_dir = r"c:\Users\muska\OneDrive\Desktop\ResearchFacultyMonitoringSystem\frontend\src\pages"
os.makedirs(pages_dir, exist_ok=True)

pages = {
    "MyProfile.tsx": """import { useEffect, useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import api from '../services/api';

export default function MyProfile() {
  const { user } = useAuth();
  const [profile, setProfile] = useState<any>(null);

  useEffect(() => {
    if (user?.id) {
      // For now, let's assume we map the user ID or just fetch a faculty record directly. 
      // The user record has faculty_id. Since the auth /me endpoint didn't return it natively without a join,
      // we'll fetch the first faculty profile as a fallback for the admin.
      api.get('/api/v1/faculty').then(res => {
         if (res.data.data.length > 0) {
            api.get(`/api/v1/faculty/${res.data.data[0].id}`).then(pRes => setProfile(pRes.data));
         }
      });
    }
  }, [user]);

  if (!profile) return <div className="p-6">Loading profile...</div>;

  return (
    <div className="space-y-6">
      <div className="glass-card p-8">
        <h2 className="text-2xl font-bold mb-2">{profile.title_prefix} {profile.first_name} {profile.last_name}</h2>
        <p className="text-blue-300">{profile.designation} • {profile.department}</p>
        <p className="text-gray-400 mt-2">{profile.institutional_email}</p>
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div className="glass-card p-6">
          <h3 className="font-bold mb-4">External Identifiers</h3>
          <ul className="space-y-2">
            {profile.identifiers.map((id: any) => (
              <li key={id.type} className="flex justify-between p-3 bg-white/5 rounded">
                <span className="font-medium">{id.type}</span>
                <span className="text-gray-300">{id.value}</span>
                {id.verified && <span className="text-green-400 text-xs border border-green-500/30 px-2 py-1 rounded">Verified</span>}
              </li>
            ))}
          </ul>
        </div>
        
        <div className="glass-card p-6">
          <h3 className="font-bold mb-4">Citation Metrics</h3>
          {profile.metric_snapshots.length > 0 ? (
            <div className="space-y-2">
               <p>Citations: {profile.metric_snapshots[0].total_citations}</p>
               <p>h-index: {profile.metric_snapshots[0].h_index}</p>
               <p>i10-index: {profile.metric_snapshots[0].i10_index}</p>
            </div>
          ) : <p className="text-gray-400">No metrics available.</p>}
        </div>
      </div>
    </div>
  );
}
""",
    "MyPublications.tsx": """import { useEffect, useState } from 'react';
import api from '../services/api';
import { Search } from 'lucide-react';

export default function MyPublications() {
  const [pubs, setPubs] = useState<any[]>([]);

  useEffect(() => {
    // Fetch all for demo, ideally filter by faculty_id
    api.get('/api/v1/publications/').then(res => setPubs(res.data.data));
  }, []);

  return (
    <div className="space-y-6">
      <div className="glass-card p-6 flex justify-between items-center">
        <h2 className="text-2xl font-bold">My Publications</h2>
        <div className="relative">
          <Search className="absolute left-3 top-2.5 text-gray-400 w-4 h-4" />
          <input type="text" placeholder="Search DOI or title..." className="pl-9 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg text-sm focus:border-blue-500 outline-none text-white" />
        </div>
      </div>

      <div className="glass-card overflow-hidden">
        <table className="w-full text-left text-sm">
          <thead className="bg-white/5 border-b border-white/10">
            <tr>
              <th className="p-4 font-medium text-gray-300">Title</th>
              <th className="p-4 font-medium text-gray-300">Year</th>
              <th className="p-4 font-medium text-gray-300">Venue</th>
              <th className="p-4 font-medium text-gray-300">Citations</th>
              <th className="p-4 font-medium text-gray-300">Verification</th>
            </tr>
          </thead>
          <tbody>
            {pubs.map(p => (
              <tr key={p.id} className="border-b border-white/5 hover:bg-white/5">
                <td className="p-4 font-medium text-blue-300 max-w-md truncate">{p.title}</td>
                <td className="p-4">{p.year}</td>
                <td className="p-4 text-gray-400">{p.journal_name || p.conference_name}</td>
                <td className="p-4">{p.citation_count}</td>
                <td className="p-4">
                  <span className={`px-2 py-1 rounded text-xs ${p.verification_status.includes('verified') ? 'bg-green-500/20 text-green-400' : 'bg-yellow-500/20 text-yellow-400'}`}>
                    {p.verification_status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
""",
    "VerificationQueue.tsx": """import { useEffect, useState } from 'react';
import api from '../services/api';
import { CheckSquare, XCircle, CheckCircle2 } from 'lucide-react';

export default function VerificationQueue() {
  const [tasks, setTasks] = useState<any[]>([]);

  useEffect(() => {
    api.get('/api/v1/review/queue').then(res => setTasks(res.data.data)).catch(() => setTasks([]));
  }, []);

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold flex items-center gap-2">
        <CheckSquare className="text-blue-400" /> Verification Queue
      </h2>
      
      <div className="grid gap-4">
        {tasks.length === 0 ? (
          <div className="glass-card p-8 text-center text-gray-400">No pending verification tasks.</div>
        ) : (
          tasks.map(task => (
            <div key={task.id} className="glass-card p-6 flex justify-between items-center">
              <div>
                <h3 className="font-bold text-lg">{task.task_type.replace('_', ' ').toUpperCase()}</h3>
                <p className="text-gray-300 mt-1">{task.reason}</p>
                <p className="text-sm text-gray-500 mt-2">Confidence: {task.confidence_score} | Created: {new Date(task.created_at).toLocaleDateString()}</p>
              </div>
              <div className="flex gap-2">
                <button className="px-4 py-2 bg-green-500/20 text-green-400 hover:bg-green-500/30 rounded flex items-center gap-2 transition-colors">
                  <CheckCircle2 size={16} /> Approve
                </button>
                <button className="px-4 py-2 bg-red-500/20 text-red-400 hover:bg-red-500/30 rounded flex items-center gap-2 transition-colors">
                  <XCircle size={16} /> Reject
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
""",
    "ResearchImpact.tsx": """import { useEffect, useState } from 'react';
import api from '../services/api';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

export default function ResearchImpact() {
  const [trends, setTrends] = useState([]);
  const [citationTrends, setCitationTrends] = useState([]);

  useEffect(() => {
    api.get('/api/v1/analytics/publication-trends').then(res => setTrends(res.data.trends));
    api.get('/api/v1/analytics/citation-trends').then(res => setCitationTrends(res.data.trends));
  }, []);

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Research Impact</h2>
      
      <div className="grid grid-cols-2 gap-6">
        <div className="glass-card p-6 h-80">
          <h3 className="font-bold mb-4">Publication Output by Year</h3>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={trends}>
              <XAxis dataKey="year" stroke="#94a3b8" />
              <YAxis stroke="#94a3b8" />
              <Tooltip contentStyle={{ backgroundColor: '#1c2744', border: 'none', borderRadius: '8px', color: '#fff' }} />
              <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        
        <div className="glass-card p-6 h-80">
          <h3 className="font-bold mb-4">Citation Growth</h3>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={citationTrends}>
              <XAxis dataKey="year" stroke="#94a3b8" />
              <YAxis stroke="#94a3b8" />
              <Tooltip contentStyle={{ backgroundColor: '#1c2744', border: 'none', borderRadius: '8px', color: '#fff' }} />
              <Bar dataKey="citations" fill="#10b981" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
""",
    "ResearchIntegrity.tsx": """import { useEffect, useState } from 'react';
import api from '../services/api';
import { ShieldAlert, AlertTriangle } from 'lucide-react';

export default function ResearchIntegrity() {
  const [stats, setStats] = useState<any>({});

  useEffect(() => {
    api.get('/api/v1/analytics/integrity-stats').then(res => setStats(res.data));
  }, []);

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold flex items-center gap-2">
        <ShieldAlert className="text-blue-400" /> Research Integrity Dashboard
      </h2>
      
      <div className="grid grid-cols-4 gap-6">
        <div className="glass-card p-6 border-b-4 border-green-500">
          <p className="text-gray-400 text-sm">LOW RISK</p>
          <p className="text-3xl font-bold mt-2">{stats.low || 0}</p>
        </div>
        <div className="glass-card p-6 border-b-4 border-yellow-500">
          <p className="text-gray-400 text-sm">MEDIUM RISK</p>
          <p className="text-3xl font-bold mt-2">{stats.medium || 0}</p>
        </div>
        <div className="glass-card p-6 border-b-4 border-red-500">
          <p className="text-gray-400 text-sm">HIGH RISK</p>
          <p className="text-3xl font-bold mt-2">{stats.high || 0}</p>
        </div>
        <div className="glass-card p-6 border-b-4 border-orange-500">
          <p className="text-gray-400 text-sm">REVIEW REQUIRED</p>
          <p className="text-3xl font-bold mt-2">{stats.review_required || 0}</p>
        </div>
      </div>
      
      <div className="glass-card p-6">
        <h3 className="font-bold mb-4">Flagged Items</h3>
        <p className="text-gray-400">Select a risk category above to view affected publications and exact risk reasons (e.g., missing DOI, conflicting publishers).</p>
      </div>
    </div>
  );
}
""",
    "ResearchSearch.tsx": """import { useState } from 'react';
import api from '../services/api';
import { Search } from 'lucide-react';

export default function ResearchSearch() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<any[]>([]);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query) return;
    const res = await api.get(`/api/v1/publications/?search=${encodeURIComponent(query)}`);
    setResults(res.data.data);
  };

  return (
    <div className="space-y-6">
      <div className="glass-card p-8 text-center max-w-2xl mx-auto mt-10">
        <h2 className="text-3xl font-bold mb-6">Global Scholarly Search</h2>
        <form onSubmit={handleSearch} className="relative">
          <Search className="absolute left-4 top-3.5 text-gray-400 w-5 h-5" />
          <input 
            type="text" 
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search publications, faculty, DOIs, keywords..." 
            className="w-full pl-12 pr-4 py-3 bg-white/5 border border-white/20 rounded-xl text-lg focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none text-white transition-all" 
          />
        </form>
      </div>

      {results.length > 0 && (
        <div className="glass-card p-6">
          <h3 className="font-bold mb-4">Search Results ({results.length})</h3>
          <ul className="space-y-4">
            {results.map(r => (
              <li key={r.id} className="p-4 bg-white/5 rounded-lg border border-white/10">
                <p className="font-medium text-blue-300 text-lg">{r.title}</p>
                <p className="text-sm text-gray-400 mt-1">{r.authors.map((a:any) => a.name).join(', ')}</p>
                <p className="text-xs text-gray-500 mt-1">{r.journal_name || r.conference_name} • {r.year} • DOI: {r.doi}</p>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
""",
    "ResearchAreas.tsx": """import { useEffect, useState } from 'react';
import api from '../services/api';

export default function ResearchAreas() {
  const [areas, setAreas] = useState<any[]>([]);

  useEffect(() => {
    api.get('/api/v1/analytics/research-areas').then(res => setAreas(res.data.areas));
  }, []);

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Research Areas Explorer</h2>
      <div className="grid grid-cols-3 gap-6">
        {areas.map(area => (
          <div key={area.name} className="glass-card p-6 hover:-translate-y-1 transition-transform cursor-pointer">
            <h3 className="text-xl font-bold text-blue-300 mb-2">{area.name}</h3>
            <p className="text-gray-400">{area.count} verified publications</p>
          </div>
        ))}
      </div>
    </div>
  );
}
""",
    "Collaborations.tsx": """import { useEffect, useState } from 'react';
import api from '../services/api';
import { Network } from 'lucide-react';

export default function Collaborations() {
  const [data, setData] = useState<any>({nodes:[], edges:[]});

  useEffect(() => {
    api.get('/api/v1/analytics/collaborations').then(res => setData(res.data));
  }, []);

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold flex items-center gap-2">
        <Network className="text-blue-400" /> Collaborations Network
      </h2>
      <div className="glass-card p-12 text-center h-[500px] flex flex-col justify-center items-center">
        {data.nodes.length === 0 ? (
          <>
            <Network className="w-16 h-16 text-gray-500 mb-4 opacity-50" />
            <p className="text-gray-400 text-lg">Collaboration intelligence will appear as verified attribution data grows.</p>
          </>
        ) : (
           <p>Network visualization loading...</p>
        )}
      </div>
    </div>
  );
}
""",
    "Opportunities.tsx": """import { useEffect, useState } from 'react';
import api from '../services/api';

export default function Opportunities() {
  const [ops, setOps] = useState([]);

  useEffect(() => {
    api.get('/api/v1/analytics/opportunities').then(res => setOps(res.data));
  }, []);

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Research Opportunities</h2>
      <div className="glass-card p-8 text-center">
        {ops.length === 0 ? (
          <p className="text-gray-400">No verified opportunities at this time. Recommendations will appear based on your research areas.</p>
        ) : (
          <p>List of opportunities...</p>
        )}
      </div>
    </div>
  );
}
""",
    "ResearchPipeline.tsx": """import { useEffect, useState } from 'react';
import api from '../services/api';
import { CheckCircle2, Clock } from 'lucide-react';

export default function ResearchPipeline() {
  const [agents, setAgents] = useState<any[]>([]);

  useEffect(() => {
    api.get('/api/v1/agents/status').then(res => setAgents(res.data.agents));
  }, []);

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Research Pipeline</h2>
      <div className="grid grid-cols-3 gap-6">
        {agents.map((agent, i) => (
          <div key={agent.name} className="glass-card p-6">
            <div className="flex justify-between items-start mb-4">
              <div className="w-8 h-8 rounded-full bg-blue-900/50 flex items-center justify-center text-xs font-bold border border-blue-500/30">
                {i + 1}
              </div>
              {agent.phase <= 10 ? (
                 <span className="flex items-center gap-1 text-xs text-green-400 bg-green-500/10 px-2 py-1 rounded border border-green-500/20"><CheckCircle2 size={12}/> Completed</span>
              ) : (
                 <span className="flex items-center gap-1 text-xs text-gray-400 bg-gray-500/10 px-2 py-1 rounded border border-gray-500/20"><Clock size={12}/> Planned</span>
              )}
            </div>
            <h3 className="font-bold">{agent.name}</h3>
            <p className="text-sm text-gray-400 mt-1">Phase {agent.phase}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
""",
    "KnowledgeGraph.tsx": """import { useEffect, useState } from 'react';
import api from '../services/api';
import { Network } from 'lucide-react';

export default function KnowledgeGraph() {
  const [data, setData] = useState<any>({nodes:[], edges:[]});

  useEffect(() => {
    api.get('/api/v1/analytics/knowledge-graph').then(res => setData(res.data));
  }, []);

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Knowledge Graph</h2>
      <div className="glass-card p-12 text-center h-[600px] flex flex-col justify-center items-center">
        {data.nodes.length === 0 ? (
          <>
            <Network className="w-16 h-16 text-gray-500 mb-4 opacity-50" />
            <p className="text-gray-400 text-lg">Graph structure computing. Entities will appear once indexed.</p>
          </>
        ) : (
           <p>Graph visualization loading...</p>
        )}
      </div>
    </div>
  );
}
""",
    "ResearchAssistant.tsx": """import { useState } from 'react';
import api from '../services/api';
import { Bot, Send } from 'lucide-react';

export default function ResearchAssistant() {
  const [msg, setMsg] = useState('');
  const [reply, setReply] = useState('');

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!msg) return;
    try {
      const res = await api.post('/api/v1/agents/chat', { message: msg });
      setReply(res.data.reply);
      setMsg('');
    } catch(e) {}
  };

  return (
    <div className="max-w-4xl mx-auto h-[80vh] flex flex-col glass-card">
      <div className="p-6 border-b border-white/10 flex items-center gap-3">
        <div className="w-10 h-10 rounded-full bg-blue-600 flex items-center justify-center">
          <Bot className="text-white" />
        </div>
        <div>
          <h2 className="font-bold text-lg">Research Intelligence Assistant</h2>
          <p className="text-xs text-blue-300">Agent 13 — Planned State</p>
        </div>
      </div>
      
      <div className="flex-1 p-6 overflow-y-auto flex flex-col justify-end space-y-4">
        {reply && (
          <div className="bg-white/10 self-start max-w-[80%] rounded-2xl rounded-tl-sm p-4 text-sm text-blue-100">
            {reply}
          </div>
        )}
      </div>

      <div className="p-4 border-t border-white/10">
        <form onSubmit={handleSend} className="relative">
          <input 
            type="text" 
            value={msg}
            onChange={(e) => setMsg(e.target.value)}
            placeholder="Ask about your publications, metrics, or research areas..."
            className="w-full bg-white/5 border border-white/10 rounded-full pl-6 pr-12 py-3 text-sm focus:border-blue-500 outline-none"
          />
          <button type="submit" className="absolute right-2 top-1.5 p-2 bg-blue-600 hover:bg-blue-500 rounded-full transition-colors">
            <Send size={16} />
          </button>
        </form>
      </div>
    </div>
  );
}
""",
    "Reports.tsx": """export default function Reports() {
  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Reports Workspace</h2>
      <div className="grid grid-cols-2 gap-6">
        <div className="glass-card p-6">
          <h3 className="font-bold mb-2">Accreditation Reports</h3>
          <p className="text-sm text-gray-400 mb-4">Export NAAC / NBA formatted publication data.</p>
          <button className="px-4 py-2 bg-blue-600/20 border border-blue-500/30 text-blue-400 rounded hover:bg-blue-600/30">Generate PDF</button>
        </div>
        <div className="glass-card p-6">
          <h3 className="font-bold mb-2">Faculty Summary</h3>
          <p className="text-sm text-gray-400 mb-4">Export total verified research output.</p>
          <button className="px-4 py-2 bg-blue-600/20 border border-blue-500/30 text-blue-400 rounded hover:bg-blue-600/30">Generate CSV</button>
        </div>
      </div>
    </div>
  );
}
""",
    "Analytics.tsx": """import { useEffect, useState } from 'react';
import api from '../services/api';
import { BarChart3 } from 'lucide-react';

export default function Analytics() {
  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold flex items-center gap-2">
        <BarChart3 className="text-blue-400" /> Advanced Analytics
      </h2>
      <div className="glass-card p-8 text-center text-gray-400">
        Analytics module initialized. Pulling data from Phase 1-10 endpoints...
      </div>
    </div>
  );
}
""",
    "Notifications.tsx": """import { useEffect, useState } from 'react';
import api from '../services/api';
import { Bell } from 'lucide-react';

export default function Notifications() {
  const [notifs, setNotifs] = useState<any[]>([]);

  useEffect(() => {
    api.get('/api/v1/analytics/notifications').then(res => setNotifs(res.data));
  }, []);

  return (
    <div className="space-y-6 max-w-3xl">
      <h2 className="text-2xl font-bold flex items-center gap-2">
        <Bell className="text-blue-400" /> Notifications
      </h2>
      <div className="space-y-4">
        {notifs.map(n => (
          <div key={n.id} className="glass-card p-4 border-l-4 border-blue-500">
            <div className="flex justify-between items-start">
              <h3 className="font-bold text-white">{n.title}</h3>
              <span className="text-xs text-gray-500">{new Date(n.date).toLocaleString()}</span>
            </div>
            <p className="text-sm text-gray-400 mt-1">{n.message}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
""",
    "Settings.tsx": """import { useEffect, useState } from 'react';
import api from '../services/api';

export default function Settings() {
  const [settings, setSettings] = useState<any>(null);

  useEffect(() => {
    api.get('/api/v1/auth/settings').then(res => setSettings(res.data));
  }, []);

  if (!settings) return null;

  return (
    <div className="space-y-6 max-w-2xl">
      <h2 className="text-2xl font-bold">Settings</h2>
      
      <div className="glass-card p-6">
        <h3 className="font-bold mb-4 border-b border-white/10 pb-2">Research Source Configuration</h3>
        <p className="text-sm text-gray-400 mb-4">API credentials remain secure server-side.</p>
        
        <div className="space-y-3">
          {['OpenAlex', 'Crossref', 'Scopus', 'Web of Science'].map(source => (
            <div key={source} className="flex justify-between items-center bg-white/5 p-3 rounded">
              <span>{source}</span>
              {settings.api_keys_configured.includes(source.toLowerCase()) ? (
                <span className="text-green-400 text-xs px-2 py-1 bg-green-500/20 rounded">Configured</span>
              ) : (
                <span className="text-gray-500 text-xs px-2 py-1 bg-gray-500/20 rounded">Not Configured</span>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
"""
}

for filename, code in pages.items():
    path = os.path.join(pages_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)

print("Pages created successfully.")
