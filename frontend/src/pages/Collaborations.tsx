import { useEffect, useState } from 'react';
import api from '../services/api';
import { 
  Network, 
  Users, 
  Share2, 
  Building2, 
  Search, 
  Filter, 
  BookOpen,
  Sparkles
} from 'lucide-react';

interface CollabNode {
  id: string;
  name: string;
  department: string;
  designation: string;
  email: string;
  publication_count: number;
  citations: number;
  topics: string[];
  is_focus?: boolean;
}

interface CollabEdge {
  id: string;
  source: string;
  target: string;
  source_name: string;
  target_name: string;
  weight: number;
  shared_topics: string[];
  relationship: string;
}

export default function Collaborations() {
  const [nodes, setNodes] = useState<CollabNode[]>([]);
  const [edges, setEdges] = useState<CollabEdge[]>([]);
  const [summary, setSummary] = useState({ total_nodes: 0, total_edges: 0, departments_count: 0 });
  const [loading, setLoading] = useState(true);
  const [selectedDept, setSelectedDept] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedNode, setSelectedNode] = useState<CollabNode | null>(null);

  useEffect(() => {
    fetchCollaborations();
  }, [selectedDept]);

  const fetchCollaborations = async () => {
    setLoading(true);
    try {
      const deptParam = selectedDept !== 'all' ? `?department=${selectedDept}` : '';
      const res = await api.get(`/api/v1/analytics/collaborations${deptParam}`);
      setNodes(res.data.nodes || []);
      setEdges(res.data.edges || []);
      setSummary({
        total_nodes: res.data.total_nodes || 0,
        total_edges: res.data.total_edges || 0,
        departments_count: res.data.departments_count || 0,
      });
      if (res.data.nodes && res.data.nodes.length > 0 && !selectedNode) {
        setSelectedNode(res.data.nodes[0]);
      }
    } catch (err) {
      console.error('Failed to load collaborations:', err);
    } finally {
      setLoading(false);
    }
  };

  const filteredNodes = nodes.filter(n => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      n.name.toLowerCase().includes(q) ||
      n.department.toLowerCase().includes(q) ||
      n.topics.some(t => t.toLowerCase().includes(q))
    );
  });

  const getNodeEdges = (nodeId: string) => {
    return edges.filter(e => e.source === nodeId || e.target === nodeId);
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white/90 backdrop-blur-md p-6 rounded-2xl border border-gray-200/80 shadow-sm">
        <div>
          <div className="flex items-center gap-2">
            <div className="p-2 bg-blue-50 text-blue-700 rounded-lg border border-blue-100">
              <Network size={24} />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Collaboration Intelligence Network</h1>
              <p className="text-sm text-gray-500 mt-0.5">
                Co-authorship clusters, shared research affinities, and cross-departmental alliances.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="relative">
            <Filter className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={14} />
            <select
              value={selectedDept}
              onChange={e => setSelectedDept(e.target.value)}
              className="pl-8 pr-4 py-2 text-xs font-semibold bg-white border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-100 focus:border-blue-400"
            >
              <option value="all">All Departments</option>
              <option value="CSE">Computer Science & Eng (CSE)</option>
              <option value="ACSE">Advanced Computer Science (ACSE)</option>
              <option value="EEE">Electrical & Electronics (EEE)</option>
              <option value="MECH">Mechanical Engineering (MECH)</option>
            </select>
          </div>
        </div>
      </div>

      {/* KPI Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white/90 backdrop-blur-md p-5 rounded-2xl border border-gray-200/80 shadow-sm flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-blue-50 border border-blue-100 flex items-center justify-center text-blue-600 font-bold">
            <Users size={22} />
          </div>
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Faculty Researchers</p>
            <p className="text-2xl font-extrabold text-gray-900 mt-0.5">{summary.total_nodes}</p>
          </div>
        </div>

        <div className="bg-white/90 backdrop-blur-md p-5 rounded-2xl border border-gray-200/80 shadow-sm flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-emerald-50 border border-emerald-100 flex items-center justify-center text-emerald-600 font-bold">
            <Share2 size={22} />
          </div>
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Active Linkages</p>
            <p className="text-2xl font-extrabold text-gray-900 mt-0.5">{summary.total_edges}</p>
          </div>
        </div>

        <div className="bg-white/90 backdrop-blur-md p-5 rounded-2xl border border-gray-200/80 shadow-sm flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-purple-50 border border-purple-100 flex items-center justify-center text-purple-600 font-bold">
            <Building2 size={22} />
          </div>
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Connected Departments</p>
            <p className="text-2xl font-extrabold text-gray-900 mt-0.5">{summary.departments_count}</p>
          </div>
        </div>

        <div className="bg-white/90 backdrop-blur-md p-5 rounded-2xl border border-gray-200/80 shadow-sm flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-amber-50 border border-amber-100 flex items-center justify-center text-amber-600 font-bold">
            <Sparkles size={22} />
          </div>
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Network Density</p>
            <p className="text-2xl font-extrabold text-gray-900 mt-0.5">
              {summary.total_nodes > 0 ? (summary.total_edges / summary.total_nodes).toFixed(1) : 0}x
            </p>
          </div>
        </div>
      </div>

      {/* Main Network View */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Researchers List Column */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={16} />
              <input
                type="text"
                placeholder="Search faculty by name, department, or topic..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-4 py-2 text-xs bg-white border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-100 focus:border-blue-400 shadow-sm"
              />
            </div>
            <span className="text-xs text-gray-500 font-medium">
              Showing {filteredNodes.length} faculty
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5 max-h-[600px] overflow-y-auto pr-1 custom-scrollbar">
            {loading ? (
              <div className="col-span-2 p-12 text-center text-gray-400 bg-white/80 rounded-2xl border border-gray-200">
                Loading research network...
              </div>
            ) : filteredNodes.length === 0 ? (
              <div className="col-span-2 p-12 text-center text-gray-400 bg-white/80 rounded-2xl border border-gray-200">
                No faculty matching query.
              </div>
            ) : (
              filteredNodes.map(node => {
                const nodeEdges = getNodeEdges(node.id);
                const isSelected = selectedNode?.id === node.id;
                return (
                  <div
                    key={node.id}
                    onClick={() => setSelectedNode(node)}
                    className={`p-4 rounded-2xl border transition-all cursor-pointer ${
                      isSelected
                        ? 'bg-blue-50/80 border-blue-400 shadow-md ring-2 ring-blue-100'
                        : 'bg-white/90 border-gray-200/80 hover:border-blue-300 hover:shadow-sm'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <div>
                        <h3 className="font-bold text-gray-900 text-sm">{node.name}</h3>
                        <p className="text-xs text-gray-500">{node.designation}</p>
                      </div>
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-100 text-blue-800 border border-blue-200">
                        {node.department}
                      </span>
                    </div>

                    <div className="flex items-center gap-3 text-xs text-gray-600 my-2.5">
                      <span className="inline-flex items-center gap-1 font-semibold">
                        <BookOpen size={13} className="text-blue-600" /> {node.publication_count} Works
                      </span>
                      <span className="inline-flex items-center gap-1 font-semibold text-emerald-700">
                        <Share2 size={13} /> {nodeEdges.length} Collabs
                      </span>
                    </div>

                    {node.topics.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-2">
                        {node.topics.map((t, idx) => (
                          <span
                            key={idx}
                            className="text-[10px] font-medium px-2 py-0.5 rounded-md bg-gray-100 text-gray-700 capitalize"
                          >
                            {t}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Selected Node Details & Connected Collaborators */}
        <div className="space-y-4">
          <div className="bg-white/95 backdrop-blur-md p-6 rounded-2xl border border-gray-200 shadow-sm sticky top-20">
            {selectedNode ? (
              <div className="space-y-4">
                <div className="border-b border-gray-100 pb-4">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-blue-600 bg-blue-50 px-2.5 py-1 rounded-full border border-blue-200">
                    Selected Researcher Profile
                  </span>
                  <h2 className="text-xl font-extrabold text-gray-900 mt-2">{selectedNode.name}</h2>
                  <p className="text-xs text-gray-500 font-medium">{selectedNode.designation} • {selectedNode.department}</p>
                  {selectedNode.email && (
                    <p className="text-xs text-blue-600 font-mono mt-1">{selectedNode.email}</p>
                  )}
                </div>

                <div className="grid grid-cols-2 gap-2 text-center">
                  <div className="p-3 bg-gray-50 rounded-xl border border-gray-100">
                    <p className="text-[10px] uppercase font-bold text-gray-400">Publications</p>
                    <p className="text-lg font-bold text-gray-900">{selectedNode.publication_count}</p>
                  </div>
                  <div className="p-3 bg-gray-50 rounded-xl border border-gray-100">
                    <p className="text-[10px] uppercase font-bold text-gray-400">Collaborations</p>
                    <p className="text-lg font-bold text-blue-600">{getNodeEdges(selectedNode.id).length}</p>
                  </div>
                </div>

                <div>
                  <h4 className="text-xs font-bold text-gray-700 uppercase tracking-wider mb-2">Connected Research Partners</h4>
                  <div className="space-y-2 max-h-64 overflow-y-auto custom-scrollbar">
                    {getNodeEdges(selectedNode.id).length === 0 ? (
                      <p className="text-xs text-gray-400 py-4 text-center">No direct co-authorship links detected yet.</p>
                    ) : (
                      getNodeEdges(selectedNode.id).map(edge => {
                        const partnerId = edge.source === selectedNode.id ? edge.target : edge.source;
                        const partnerName = edge.source === selectedNode.id ? edge.target_name : edge.source_name;
                        const partner = nodes.find(n => n.id === partnerId);

                        return (
                          <div
                            key={edge.id}
                            onClick={() => partner && setSelectedNode(partner)}
                            className="p-3 rounded-xl bg-gray-50/80 border border-gray-100 hover:bg-blue-50/60 hover:border-blue-200 transition-colors cursor-pointer"
                          >
                            <div className="flex items-center justify-between">
                              <p className="text-xs font-bold text-gray-900">{partnerName}</p>
                              <span className="text-[10px] font-semibold text-blue-700 bg-blue-100 px-1.5 py-0.5 rounded">
                                {edge.relationship}
                              </span>
                            </div>
                            {edge.shared_topics && edge.shared_topics.length > 0 && (
                              <p className="text-[11px] text-gray-500 mt-1">
                                Shared: {edge.shared_topics.map(t => t).join(', ')}
                              </p>
                            )}
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-center py-16 text-gray-400">
                <Users size={32} className="mx-auto mb-2 opacity-50" />
                <p className="text-sm font-medium">Select a researcher to view collaboration intelligence.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
