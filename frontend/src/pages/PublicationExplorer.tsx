export default function PublicationExplorer() {
  return (
    <div>
      <div className="mb-6">
        <h2
          className="text-2xl font-bold"
          style={{ color: 'var(--color-text-primary)' }}
        >
          Publication Explorer
        </h2>
        <p style={{ color: 'var(--color-text-secondary)' }}>
          Search, filter, and verify institutional research publications
        </p>
      </div>

      <div className="glass-card p-12 text-center">
        <div className="text-4xl mb-4">📚</div>
        <p
          className="text-lg mb-2"
          style={{ color: 'var(--color-text-secondary)' }}
        >
          Publication data will appear after discovery pipeline runs
        </p>
        <p
          className="text-sm"
          style={{ color: 'var(--color-text-muted)' }}
        >
          Automated Publication Discovery → Normalization & Deduplication Pipeline
        </p>
      </div>
    </div>
  )
}
