import { useEffect, useState } from 'react';
import api from '../services/api';
import { 
  Network, 
  Layers, 
  Building2, 
  BookOpen, 
  Tag, 
  Compass, 
  Search
} from 'lucide-react';

interface KGNode {
  id: string;
  label: string;
  type: string;
  group: string;
  department?: string;
  designation?: string;
  year?: number;
  citations?: number;
  full_title?: string;
  val: number;
}

interface KGEdge {
  source: string;
  target: string;
  label: string;
}

export default function KnowledgeGraph() {
  const [nodes, setNodes] = useState<KGNode[]>([]);
  const [edges, setEdges] = useState<KGEdge[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedType, setSelectedType] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedNode, setSelectedNode] = useState<KGNode | null>(null);

  useEffect(() => {
    fetchKnowledgeGraph();
  }, []);

  const fetchKnowledgeGraph = async () => {
    setLoading(true);
    try {
      const res = await api.get('/api/v1/analytics/knowledge-graph');
      setNodes(res.data.nodes || []);
      setEdges(res.data.edges || []);
      if (res.data.nodes && res.data.nodes.length > 0) {
        setSelectedNode(res.data.nodes[0]);
      }
    } catch (err) {
      console.error('Failed to load knowledge graph:', err);
    } finally {
      setLoading(false);
    }
  };

  const filteredNodes = nodes.filter(n => {
    const matchesType = selectedType === 'all' || n.type.toLowerCase() === selectedType.toLowerCase();
    if (!matchesType) return false;
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      n.label.toLowerCase().includes(q) ||
      (n.full_title && n.full_title.toLowerCase().includes(q)) ||
      (n.department && n.department.toLowerCase().includes(q))
    );
  });

  const getNodeConnections = (nodeId: string) => {
    return edges.filter(e => e.source === nodeId || e.target === nodeId);
  };

  const getNodeBadgeColor = (type: string) => {
    switch (type.toLowerCase()) {
      case 'department':
        return 'bg-purple-100 text-purple-800 border-purple-200';
      case 'faculty':
        return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'publication':
        return 'bg-emerald-100 text-emerald-800 border-emerald-200';
      case 'research area':
        return 'bg-amber-100 text-amber-800 border-amber-200';
      case 'venue':
        return 'bg-rose-100 text-rose-800 border-rose-200';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const getNodeIcon = (type: string) => {
    switch (type.toLowerCase()) {
      case 'department':
        return <Building2 size={16} className="text-purple-600" />;
      case 'faculty':
        return <Compass size={16} className="text-blue-600" />;
      case 'publication':
        return <BookOpen size={16} className="text-emerald-600" />;
      case 'research area':
        return <Tag size={16} className="text-amber-600" />;
      case 'venue':
        return <Layers size={16} className="text-rose-600" />;
      default:
        return <Network size={16} className="text-gray-600" />;
    }
  };

  const typeCounts = {
    all: nodes.length,
    faculty: nodes.filter(n => n.type.toLowerCase() === 'faculty').length,
    publication: nodes.filter(n => n.type.toLowerCase() === 'publication').length,
    department: nodes.filter(n => n.type.toLowerCase() === 'department').length,
    'research area': nodes.filter(n => n.type.toLowerCase() === 'research area').length,
    venue: nodes.filter(n => n.type.toLowerCase() === 'venue').length,
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white/90 backdrop-blur-md p-6 rounded-2xl border border-gray-200/80 shadow-sm">
        <div>
          <div className="flex items-center gap-2">
            <div className="p-2 bg-indigo-50 text-indigo-700 rounded-lg border border-indigo-100">
              <Network size={24} />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Institutional Knowledge Graph</h1>
              <p className="text-sm text-gray-500 mt-0.5">
                Multi-entity semantic relationships connecting departments, faculty, publications, and venues.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchKnowledgeGraph}
            className="px-4 py-2 text-xs font-semibold bg-white border border-gray-200 text-gray-700 hover:bg-gray-50 rounded-xl shadow-sm transition-colors"
          >
            Refresh Graph
          </button>
        </div>
      </div>

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3.5">
        <div className="bg-white/90 backdrop-blur-md p-4 rounded-2xl border border-gray-200/80 shadow-sm">
          <p className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">Total Entities</p>
          <p className="text-2xl font-extrabold text-gray-900 mt-0.5">{nodes.length}</p>
        </div>
        <div className="bg-white/90 backdrop-blur-md p-4 rounded-2xl border border-gray-200/80 shadow-sm">
          <p className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">Relationships</p>
          <p className="text-2xl font-extrabold text-indigo-600 mt-0.5">{edges.length}</p>
        </div>
        <div className="bg-white/90 backdrop-blur-md p-4 rounded-2xl border border-gray-200/80 shadow-sm">
          <p className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">Faculty Nodes</p>
          <p className="text-2xl font-extrabold text-blue-600 mt-0.5">{typeCounts.faculty}</p>
        </div>
        <div className="bg-white/90 backdrop-blur-md p-4 rounded-2xl border border-gray-200/80 shadow-sm">
          <p className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">Publications</p>
          <p className="text-2xl font-extrabold text-emerald-600 mt-0.5">{typeCounts.publication}</p>
        </div>
        <div className="bg-white/90 backdrop-blur-md p-4 rounded-2xl border border-gray-200/80 shadow-sm">
          <p className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">Research Venues</p>
          <p className="text-2xl font-extrabold text-rose-600 mt-0.5">{typeCounts.venue}</p>
        </div>
      </div>

      {/* Filter Tabs & Search */}
      <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center justify-between">
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0 custom-scrollbar">
          {[
            { id: 'all', label: `All (${typeCounts.all})` },
            { id: 'faculty', label: `Faculty (${typeCounts.faculty})` },
            { id: 'department', label: `Departments (${typeCounts.department})` },
            { id: 'publication', label: `Publications (${typeCounts.publication})` },
            { id: 'research area', label: `Topics (${typeCounts['research area']})` },
            { id: 'venue', label: `Venues (${typeCounts.venue})` },
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setSelectedType(tab.id)}
              className={`px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-all ${
                selectedType === tab.id
                  ? 'bg-indigo-600 text-white shadow-sm'
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
            placeholder="Search entities in graph..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-4 py-1.5 text-xs bg-white border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-100 focus:border-indigo-400 shadow-sm"
          />
        </div>
      </div>

      {/* Main Graph & Inspector Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Entity List */}
        <div className="lg:col-span-2 space-y-3 max-h-[600px] overflow-y-auto pr-1 custom-scrollbar">
          {loading ? (
            <div className="p-12 text-center text-gray-400 bg-white/80 rounded-2xl border border-gray-200">
              Loading knowledge graph entities...
            </div>
          ) : filteredNodes.length === 0 ? (
            <div className="p-12 text-center text-gray-400 bg-white/80 rounded-2xl border border-gray-200">
              No graph entities found matching the criteria.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {filteredNodes.map(node => {
                const isSelected = selectedNode?.id === node.id;
                const connections = getNodeConnections(node.id);

                return (
                  <div
                    key={node.id}
                    onClick={() => setSelectedNode(node)}
                    className={`p-4 rounded-2xl border transition-all cursor-pointer ${
                      isSelected
                        ? 'bg-indigo-50/90 border-indigo-400 shadow-md ring-2 ring-indigo-100'
                        : 'bg-white/90 border-gray-200/80 hover:border-indigo-300 hover:shadow-sm'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <div className="flex items-center gap-2">
                        <div className="p-1.5 bg-gray-50 rounded-lg border border-gray-100">
                          {getNodeIcon(node.type)}
                        </div>
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${getNodeBadgeColor(node.type)}`}>
                          {node.type}
                        </span>
                      </div>
                      <span className="text-[10px] font-semibold text-gray-400">
                        {connections.length} links
                      </span>
                    </div>

                    <h3 className="font-bold text-gray-900 text-sm leading-snug">{node.label}</h3>
                    {node.department && (
                      <p className="text-xs text-gray-500 mt-0.5">{node.designation || 'Dept'} • {node.department}</p>
                    )}
                    {node.year && (
                      <p className="text-xs text-gray-500 mt-0.5">Published: {node.year} {node.citations !== undefined ? `• ${node.citations} Citations` : ''}</p>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Selected Entity Inspector */}
        <div className="space-y-4">
          <div className="bg-white/95 backdrop-blur-md p-6 rounded-2xl border border-gray-200 shadow-sm sticky top-20">
            {selectedNode ? (
              <div className="space-y-4">
                <div className="border-b border-gray-100 pb-4">
                  <div className="flex items-center gap-2 mb-2">
                    <span className={`text-[10px] font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full border ${getNodeBadgeColor(selectedNode.type)}`}>
                      {selectedNode.type}
                    </span>
                  </div>
                  <h2 className="text-lg font-extrabold text-gray-900">{selectedNode.label}</h2>
                  {selectedNode.full_title && selectedNode.full_title !== selectedNode.label && (
                    <p className="text-xs text-gray-600 mt-1 leading-relaxed">{selectedNode.full_title}</p>
                  )}
                  {selectedNode.department && (
                    <p className="text-xs text-gray-500 font-medium mt-1">{selectedNode.designation} • {selectedNode.department}</p>
                  )}
                </div>

                <div>
                  <h4 className="text-xs font-bold text-gray-700 uppercase tracking-wider mb-2.5 flex items-center justify-between">
                    <span>Graph Relations</span>
                    <span className="text-indigo-600 font-mono">{getNodeConnections(selectedNode.id).length} links</span>
                  </h4>

                  <div className="space-y-2 max-h-64 overflow-y-auto custom-scrollbar">
                    {getNodeConnections(selectedNode.id).length === 0 ? (
                      <p className="text-xs text-gray-400 text-center py-4">No direct links detected.</p>
                    ) : (
                      getNodeConnections(selectedNode.id).map((edge, idx) => {
                        const targetId = edge.source === selectedNode.id ? edge.target : edge.source;
                        const targetNode = nodes.find(n => n.id === targetId);
                        const isOutbound = edge.source === selectedNode.id;

                        return (
                          <div
                            key={idx}
                            onClick={() => targetNode && setSelectedNode(targetNode)}
                            className="p-3 rounded-xl bg-gray-50/80 border border-gray-100 hover:bg-indigo-50/60 hover:border-indigo-200 transition-colors cursor-pointer"
                          >
                            <div className="flex items-center justify-between gap-2">
                              <span className="text-[10px] font-bold text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded-md border border-indigo-100">
                                {isOutbound ? `→ ${edge.label}` : `← ${edge.label}`}
                              </span>
                              {targetNode && (
                                <span className="text-[10px] text-gray-400 font-medium">
                                  {targetNode.type}
                                </span>
                              )}
                            </div>
                            <p className="text-xs font-semibold text-gray-900 mt-1.5 line-clamp-2">
                              {targetNode ? targetNode.label : targetId}
                            </p>
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-center py-16 text-gray-400">
                <Network size={32} className="mx-auto mb-2 opacity-50" />
                <p className="text-sm font-medium">Select an entity to explore semantic relationships.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
