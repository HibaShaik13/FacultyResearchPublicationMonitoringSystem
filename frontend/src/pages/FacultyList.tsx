import { useState, useEffect } from 'react'

interface Faculty {
  id: string
  raw_name: string
  department: string | null
  designation: string | null
  institutional_email: string | null
  research_interests: string[] | null
  declared_publication_count: number | null
  identifiers: { type: string; value: string; verified: boolean }[]
  name_variants: string[]
}

export default function FacultyList() {
  const [faculty, setFaculty] = useState<Faculty[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [department, setDepartment] = useState('')

  useEffect(() => {
    const params = new URLSearchParams()
    if (search) params.set('search', search)
    if (department) params.set('department', department)

    fetch(`/api/v1/faculty/?${params}`)
      .then((r) => r.json())
      .then((data) => setFaculty(data.data || []))
      .catch(() => setFaculty([]))
      .finally(() => setLoading(false))
  }, [search, department])

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2
            className="text-2xl font-bold"
            style={{ color: 'var(--color-text-primary)' }}
          >
            Faculty Profiles
          </h2>
          <p style={{ color: 'var(--color-text-secondary)' }}>
            {faculty.length} faculty members loaded
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-6">
        <input
          type="text"
          placeholder="Search by name..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="px-4 py-2 rounded-lg text-sm flex-1"
          style={{
            background: 'var(--color-surface-800)',
            border: '1px solid rgba(90, 122, 224, 0.2)',
            color: 'var(--color-text-primary)',
            outline: 'none',
          }}
        />
        <select
          value={department}
          onChange={(e) => setDepartment(e.target.value)}
          className="px-4 py-2 rounded-lg text-sm"
          style={{
            background: 'var(--color-surface-800)',
            border: '1px solid rgba(90, 122, 224, 0.2)',
            color: 'var(--color-text-primary)',
          }}
        >
          <option value="">All Departments</option>
          <option value="CSE">CSE</option>
          <option value="EEE">EEE</option>
          <option value="MECH">MECH</option>
          <option value="ACSE">ACSE</option>
        </select>
      </div>

      {/* Faculty Grid */}
      {loading ? (
        <div className="text-center py-12" style={{ color: 'var(--color-text-muted)' }}>
          Loading faculty profiles...
        </div>
      ) : faculty.length === 0 ? (
        <div className="glass-card p-12 text-center">
          <p className="text-lg mb-2" style={{ color: 'var(--color-text-secondary)' }}>
            No faculty profiles loaded yet
          </p>
          <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
            Faculty data will appear after CSV profile import
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {faculty.map((f) => (
            <div key={f.id} className="glass-card p-5">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <h3
                    className="font-semibold"
                    style={{ color: 'var(--color-text-primary)' }}
                  >
                    {f.raw_name}
                  </h3>
                  <p
                    className="text-xs mt-0.5"
                    style={{ color: 'var(--color-text-muted)' }}
                  >
                    {f.designation}
                  </p>
                </div>
                {f.department && (
                  <span className="badge badge-review">{f.department}</span>
                )}
              </div>

              {f.institutional_email && (
                <p
                  className="text-xs mb-2"
                  style={{ color: 'var(--color-text-secondary)' }}
                >
                  ✉ {f.institutional_email}
                </p>
              )}

              {f.research_interests && f.research_interests.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mb-3">
                  {f.research_interests.slice(0, 3).map((interest) => (
                    <span
                      key={interest}
                      className="text-xs px-2 py-0.5 rounded-full"
                      style={{
                        background: 'rgba(90, 122, 224, 0.1)',
                        color: 'var(--color-brand-300)',
                        border: '1px solid rgba(90, 122, 224, 0.2)',
                      }}
                    >
                      {interest}
                    </span>
                  ))}
                </div>
              )}

              <div className="flex items-center justify-between pt-2" style={{ borderTop: '1px solid rgba(90, 122, 224, 0.1)' }}>
                <span className="text-sm" style={{ color: 'var(--color-accent-400)' }}>
                  📄 {f.declared_publication_count ?? 0} publications
                </span>
                <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                  {f.identifiers.length > 0
                    ? `${f.identifiers.length} ID(s)`
                    : 'No external IDs'}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
