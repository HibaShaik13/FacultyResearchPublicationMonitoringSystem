export default function AgentCenter() {
  const agents = [
    { name: 'Faculty Identity', phase: 2, description: 'Manages faculty profiles and external identifiers', status: 'idle' },
    { name: 'Affiliation Intelligence', phase: 2, description: 'Learns institutional affiliation variants', status: 'idle' },
    { name: 'Publication Discovery', phase: 4, description: 'Searches research sources for new publications', status: 'idle' },
    { name: 'Metadata Normalization', phase: 5, description: 'Standardizes publication metadata', status: 'idle' },
    { name: 'Deduplication', phase: 5, description: 'Identifies and merges duplicate publications', status: 'idle' },
    { name: 'Faculty Attribution', phase: 6, description: 'Links publications to VFSTR faculty', status: 'idle' },
    { name: 'Metadata Enrichment', phase: 7, description: 'Adds journal quality metrics and indexing data', status: 'idle' },
    { name: 'Research Integrity', phase: 8, description: 'Detects suspicious records and risk flags', status: 'idle' },
    { name: 'Citation Metrics', phase: 9, description: 'Tracks citations, h-index, and i10-index', status: 'idle' },
    { name: 'Verification & Evidence', phase: 6, description: 'Validates evidence chains and verification state', status: 'idle' },
    { name: 'Human Review & Verification', phase: 10, description: 'Creates review queues for human decisions', status: 'idle' },
    { name: 'Reporting & Accreditation', phase: 14, description: 'Generates reports and accreditation evidence', status: 'idle' },
    { name: 'Research Intelligence Assistant', phase: 15, description: 'Natural language research knowledge base', status: 'idle' },
  ]

  return (
    <div>
      <div className="mb-6">
        <h2
          className="text-2xl font-bold"
          style={{ color: 'var(--color-text-primary)' }}
        >
          Research Services Activity Center
        </h2>
        <p style={{ color: 'var(--color-text-secondary)' }}>
          Monitor the specialized intelligence services powering the research platform
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {agents.map((agent) => (
          <div key={agent.name} className="glass-card p-5">
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className={`agent-dot agent-dot-${agent.status}`}></span>
                <h3
                  className="font-semibold text-sm"
                  style={{ color: 'var(--color-text-primary)' }}
                >
                  {agent.name}
                </h3>
              </div>
              <span
                className="text-xs px-2 py-0.5 rounded font-medium"
                style={{
                  background: 'var(--color-surface-800)',
                  color: 'var(--color-text-muted)',
                }}
              >
                Active Service
              </span>
            </div>

            <p
              className="text-xs mb-3"
              style={{ color: 'var(--color-text-secondary)' }}
            >
              {agent.description}
            </p>

            <div
              className="flex items-center justify-between pt-2 text-xs"
              style={{
                borderTop: '1px solid rgba(90, 122, 224, 0.1)',
                color: 'var(--color-text-muted)',
              }}
            >
              <span>Last run: —</span>
              <span>Records: 0</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
