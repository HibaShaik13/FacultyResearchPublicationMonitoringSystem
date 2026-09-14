import { useEffect, useState } from 'react';
import api from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import {
  FileSpreadsheet,
  Download,
  Building,
  UserCheck,
  CheckCircle2,
  BookOpen,
  Filter,
  RefreshCw,
  Printer,
  ExternalLink,
  Table,
} from 'lucide-react';

interface AccreditationRecord {
  sl_no: number;
  publication_id: string;
  title: string;
  faculty_author: string;
  all_authors: string;
  department: string;
  journal_or_conference: string;
  year: number;
  doi: string;
  issn_isbn: string;
  indexing: string;
  verification_status: string;
  confidence_score: string;
  institutional_affiliation_verified: boolean;
}

interface AccreditationReportData {
  report_type: string;
  standard: string;
  institution: string;
  generated_at: string;
  evidence_summary: {
    total_records: number;
    verified_records: number;
    accreditation_compliance_rate: string;
    criteria_mapping: string;
  };
  records: AccreditationRecord[];
}

interface FacultyReportData {
  faculty: {
    name: string;
    department: string;
    designation: string;
    email: string;
  };
  summary: {
    total_publications: number;
    verified_publications: number;
    verification_rate: number;
    total_citations: number;
    h_index: number;
    i10_index: number;
  };
  distributions: {
    verification: Record<string, number>;
    risk: Record<string, number>;
    by_year: Record<string, number>;
    by_type: Record<string, number>;
  };
  publications: Array<{
    id: string;
    title: string;
    year: number;
    doi: string;
    journal_name: string;
    conference_name: string;
    citation_count: number;
    verification_status: string;
  }>;
}

interface DepartmentReportData {
  department: string;
  summary: {
    total_faculty: number;
    total_publications: number;
    verified_publications: number;
    verification_rate: number;
    total_citations: number;
    avg_pubs_per_faculty: number;
  };
  faculty_ranking: Array<{
    id: string;
    name: string;
    designation: string;
    email: string;
    publication_count: number;
    citation_count: number;
  }>;
}

interface InstitutionReportData {
  institution_name: string;
  kpis: {
    total_faculty: number;
    total_publications: number;
    verified_publications: number;
    verification_rate: number;
    total_citations: number;
    avg_citations_per_pub: number;
    scopus_indexed_estimate: number;
    scie_indexed_estimate: number;
  };
  departments: Array<{ department: string; faculty_count: number }>;
  annual_growth: Array<{ year: number; publications: number; citations: number }>;
}

export default function Reports() {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<'accreditation' | 'faculty' | 'department' | 'institution'>('accreditation');
  const [loading, setLoading] = useState(true);

  // Filter States
  const [standard, setStandard] = useState<'NAAC_NIRF' | 'NIRF' | 'NBA'>('NAAC_NIRF');
  const [facultyList, setFacultyList] = useState<Array<{ id: string; name: string }>>([]);
  const [selectedFacultyId, setSelectedFacultyId] = useState<string>('');
  const [selectedDept, setSelectedDept] = useState<string>('CSE');

  // Report Data
  const [accreditationData, setAccreditationData] = useState<AccreditationReportData | null>(null);
  const [facultyData, setFacultyData] = useState<FacultyReportData | null>(null);
  const [deptData, setDeptData] = useState<DepartmentReportData | null>(null);
  const [instData, setInstData] = useState<InstitutionReportData | null>(null);

  const isFaculty = user?.role === 'faculty';

  // Load faculty options
  useEffect(() => {
    if (!isFaculty) {
      api.get('/api/v1/faculty?limit=50').then((res) => {
        const facs = res.data?.data || [];
        setFacultyList(facs);
        if (facs.length > 0 && !selectedFacultyId) {
          setSelectedFacultyId(facs[0].id);
        }
      });
    } else if (user?.faculty_id) {
      setSelectedFacultyId(user.faculty_id);
    }
  }, [user]);

  // Load report data based on activeTab
  const fetchReport = async () => {
    setLoading(true);
    try {
      if (activeTab === 'accreditation') {
        const res = await api.get('/api/v1/reports/accreditation', {
          params: {
            standard,
            faculty_id: isFaculty ? user?.faculty_id : undefined,
          },
        });
        setAccreditationData(res.data);
      } else if (activeTab === 'faculty') {
        const targetId = isFaculty ? user?.faculty_id : selectedFacultyId;
        if (targetId) {
          const res = await api.get(`/api/v1/reports/faculty/${targetId}`);
          setFacultyData(res.data);
        }
      } else if (activeTab === 'department') {
        const res = await api.get(`/api/v1/reports/department/${selectedDept}`);
        setDeptData(res.data);
      } else if (activeTab === 'institution') {
        const res = await api.get('/api/v1/reports/institution');
        setInstData(res.data);
      }
    } catch (err) {
      console.error('Error fetching report', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReport();
  }, [activeTab, standard, selectedFacultyId, selectedDept]);

  const handleExportCSV = () => {
    window.open(`/api/v1/reports/export/csv?standard=${standard}`, '_blank');
  };

  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="space-y-6 pb-12 font-sans">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-white p-6 rounded-2xl border border-gray-200/80 shadow-sm">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2.5 py-0.5 rounded-full text-xs font-bold uppercase tracking-wider bg-blue-100 text-blue-800">
              Reporting & Accreditation
            </span>
            <span className="text-xs text-gray-500 font-medium">Authoritative Intelligence Packages</span>
          </div>
          <h1 className="text-2xl font-extrabold text-gray-900 mt-2 flex items-center gap-2">
            <FileSpreadsheet className="text-blue-600" size={28} />
            Research Reporting & Accreditation Workspace
          </h1>
          <p className="text-sm text-gray-600 mt-1">
            Generate audit-ready evidence packages formatted for NAAC (Criterion 3), NIRF, NBA, and institutional review.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={handleExportCSV}
            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs rounded-xl shadow-sm flex items-center gap-1.5 transition-colors"
          >
            <Download size={14} /> Export CSV
          </button>

          <button
            onClick={handlePrint}
            className="px-3.5 py-2 bg-gray-50 hover:bg-gray-100 text-gray-700 border border-gray-200 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-colors shadow-sm"
          >
            <Printer size={14} /> Print / PDF
          </button>

          <button
            onClick={fetchReport}
            className="p-2 text-gray-500 hover:text-gray-700 bg-gray-50 hover:bg-gray-100 border border-gray-200 rounded-xl transition-colors shadow-sm"
            title="Refresh Data"
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {/* Tabs Bar */}
      <div className="flex border-b border-gray-200 bg-white px-4 pt-3 rounded-2xl shadow-sm flex-wrap gap-2">
        <button
          onClick={() => setActiveTab('accreditation')}
          className={`pb-3 px-4 font-semibold text-xs sm:text-sm flex items-center gap-2 border-b-2 transition-colors ${
            activeTab === 'accreditation'
              ? 'border-blue-600 text-blue-600 font-bold'
              : 'border-transparent text-gray-500 hover:text-gray-900'
          }`}
        >
          <Table size={15} /> Accreditation Package (NAAC / NIRF)
        </button>

        <button
          onClick={() => setActiveTab('faculty')}
          className={`pb-3 px-4 font-semibold text-xs sm:text-sm flex items-center gap-2 border-b-2 transition-colors ${
            activeTab === 'faculty'
              ? 'border-blue-600 text-blue-600 font-bold'
              : 'border-transparent text-gray-500 hover:text-gray-900'
          }`}
        >
          <UserCheck size={15} /> Faculty Research Report
        </button>

        {!isFaculty && (
          <>
            <button
              onClick={() => setActiveTab('department')}
              className={`pb-3 px-4 font-semibold text-xs sm:text-sm flex items-center gap-2 border-b-2 transition-colors ${
                activeTab === 'department'
                  ? 'border-blue-600 text-blue-600 font-bold'
                  : 'border-transparent text-gray-500 hover:text-gray-900'
              }`}
            >
              <Building size={15} /> Department Summary
            </button>

            <button
              onClick={() => setActiveTab('institution')}
              className={`pb-3 px-4 font-semibold text-xs sm:text-sm flex items-center gap-2 border-b-2 transition-colors ${
                activeTab === 'institution'
                  ? 'border-blue-600 text-blue-600 font-bold'
                  : 'border-transparent text-gray-500 hover:text-gray-900'
              }`}
            >
              <BookOpen size={15} /> Institutional Overview
            </button>
          </>
        )}
      </div>

      {/* TAB 1: ACCREDITATION EVIDENCE PACKAGE */}
      {activeTab === 'accreditation' && (
        <div className="space-y-5">
          {/* Controls Bar */}
          <div className="bg-white p-4 rounded-2xl border border-gray-200 shadow-sm flex flex-col sm:flex-row justify-between items-stretch sm:items-center gap-3">
            <div className="flex items-center gap-2 text-xs">
              <Filter size={14} className="text-gray-400" />
              <span className="font-bold text-gray-600 uppercase tracking-wider">Accreditation Standard:</span>
              <select
                value={standard}
                onChange={(e: any) => setStandard(e.target.value)}
                className="bg-gray-50 border border-gray-200 text-gray-900 font-bold rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
              >
                <option value="NAAC_NIRF">NAAC 3.4.4 & NIRF Combined Output</option>
                <option value="NIRF">NIRF Research Parameters</option>
                <option value="NBA">NBA Criterion 5 (Faculty Contributions)</option>
              </select>
            </div>

            <div className="text-xs text-gray-500 font-medium">
              Mapping: <strong className="text-gray-900">{accreditationData?.evidence_summary?.criteria_mapping}</strong>
            </div>
          </div>

          {/* Metric Summary Cards */}
          {accreditationData && (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="stat-card p-5 bg-white border border-gray-200 rounded-2xl shadow-sm">
                <p className="text-xs font-bold text-gray-500 uppercase tracking-wider">Total Evidence Records</p>
                <h3 className="text-2xl font-black text-gray-900 mt-1">
                  {accreditationData.evidence_summary.total_records}
                </h3>
                <p className="text-xs text-gray-500 mt-1">Submitted scholarly works</p>
              </div>

              <div className="stat-card p-5 bg-white border border-emerald-200 rounded-2xl shadow-sm bg-emerald-50/20">
                <p className="text-xs font-bold text-emerald-800 uppercase tracking-wider">Verified Compliant Records</p>
                <h3 className="text-2xl font-black text-emerald-900 mt-1">
                  {accreditationData.evidence_summary.verified_records}
                </h3>
                <p className="text-xs text-emerald-700 mt-1 flex items-center gap-1 font-semibold">
                  <CheckCircle2 size={12} /> 100% Provenance Backed
                </p>
              </div>

              <div className="stat-card p-5 bg-white border border-blue-200 rounded-2xl shadow-sm bg-blue-50/20">
                <p className="text-xs font-bold text-blue-800 uppercase tracking-wider">Compliance Rate</p>
                <h3 className="text-2xl font-black text-blue-900 mt-1">
                  {accreditationData.evidence_summary.accreditation_compliance_rate}
                </h3>
                <p className="text-xs text-blue-700 mt-1 font-medium">Institutional QA target exceeded</p>
              </div>
            </div>
          )}

          {/* Evidence Table */}
          <div className="bg-white p-6 rounded-2xl border border-gray-200 shadow-sm space-y-4">
            <div className="flex justify-between items-center">
              <h3 className="text-lg font-bold text-gray-900">
                Accreditation Data Table ({accreditationData?.records?.length || 0} Entries)
              </h3>
              <span className="text-xs text-gray-400 font-medium">
                VFSTR Research Monitoring System • Authoritative Data
              </span>
            </div>

            {loading ? (
              <div className="py-12 text-center text-gray-500">
                <RefreshCw className="animate-spin text-blue-600 mx-auto mb-2" size={28} />
                Compiling accreditation evidence package...
              </div>
            ) : accreditationData?.records?.length === 0 ? (
              <div className="py-12 text-center text-gray-400 text-sm italic">
                No publication records match this criteria.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="border-b border-gray-200 text-gray-500 font-bold uppercase text-[11px] tracking-wider bg-gray-50/70">
                      <th className="py-3 px-3">#</th>
                      <th className="py-3 px-3">Paper Title</th>
                      <th className="py-3 px-3">Author(s)</th>
                      <th className="py-3 px-3">Dept</th>
                      <th className="py-3 px-3">Venue (Journal / Conference)</th>
                      <th className="py-3 px-3">Year</th>
                      <th className="py-3 px-3">DOI / Identifier</th>
                      <th className="py-3 px-3">Verification</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 text-gray-700">
                    {accreditationData?.records.map((row) => (
                      <tr key={row.sl_no} className="hover:bg-gray-50/80 transition-colors">
                        <td className="py-3 px-3 font-bold text-gray-400">{row.sl_no}</td>
                        <td className="py-3 px-3 font-bold text-gray-900 max-w-xs">{row.title}</td>
                        <td className="py-3 px-3 text-gray-600 truncate max-w-[140px]">{row.faculty_author}</td>
                        <td className="py-3 px-3">
                          <span className="bg-blue-50 text-blue-700 font-semibold px-2 py-0.5 rounded border border-blue-200 text-[11px]">
                            {row.department}
                          </span>
                        </td>
                        <td className="py-3 px-3 italic text-gray-600 max-w-[180px] truncate">{row.journal_or_conference}</td>
                        <td className="py-3 px-3 font-semibold text-gray-900">{row.year}</td>
                        <td className="py-3 px-3 font-mono text-[11px]">
                          {row.doi && row.doi !== 'N/A' ? (
                            <a
                              href={`https://doi.org/${row.doi.replace(/^https?:\/\/doi\.org\//, '')}`}
                              target="_blank"
                              rel="noreferrer"
                              className="text-blue-600 hover:underline flex items-center gap-1"
                            >
                              {row.doi.slice(0, 18)}... <ExternalLink size={10} />
                            </a>
                          ) : (
                            <span className="text-gray-400">N/A</span>
                          )}
                        </td>
                        <td className="py-3 px-3">
                          <span className="bg-emerald-50 text-emerald-700 font-bold px-2 py-0.5 rounded-full border border-emerald-200 text-[10px] inline-flex items-center gap-1">
                            <CheckCircle2 size={10} /> {row.verification_status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 2: FACULTY REPORT */}
      {activeTab === 'faculty' && (
        <div className="space-y-5">
          {!isFaculty && facultyList.length > 0 && (
            <div className="bg-white p-4 rounded-2xl border border-gray-200 shadow-sm flex items-center gap-3">
              <span className="text-xs font-bold text-gray-600 uppercase tracking-wider">Select Faculty Member:</span>
              <select
                value={selectedFacultyId}
                onChange={(e) => setSelectedFacultyId(e.target.value)}
                className="bg-gray-50 border border-gray-200 text-gray-900 font-bold text-xs rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
              >
                {facultyList.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.name}
                  </option>
                ))}
              </select>
            </div>
          )}

          {facultyData && (
            <>
              {/* Faculty Profile Card */}
              <div className="bg-white p-6 rounded-2xl border border-gray-200 shadow-sm flex flex-col sm:flex-row justify-between gap-4">
                <div>
                  <h3 className="text-xl font-extrabold text-gray-900">{facultyData.faculty.name}</h3>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {facultyData.faculty.designation} • Department of {facultyData.faculty.department}
                  </p>
                  <p className="text-xs font-mono text-blue-600 mt-1">{facultyData.faculty.email}</p>
                </div>

                <div className="flex gap-4 sm:border-l sm:border-gray-200 sm:pl-6">
                  <div>
                    <span className="text-[11px] font-bold text-gray-400 uppercase tracking-wider">Publications</span>
                    <h4 className="text-2xl font-black text-gray-900">{facultyData.summary.total_publications}</h4>
                  </div>
                  <div>
                    <span className="text-[11px] font-bold text-gray-400 uppercase tracking-wider">Citations</span>
                    <h4 className="text-2xl font-black text-emerald-600">{facultyData.summary.total_citations}</h4>
                  </div>
                  <div>
                    <span className="text-[11px] font-bold text-gray-400 uppercase tracking-wider">h-index</span>
                    <h4 className="text-2xl font-black text-blue-600">{facultyData.summary.h_index}</h4>
                  </div>
                </div>
              </div>

              {/* Publications List */}
              <div className="bg-white p-6 rounded-2xl border border-gray-200 shadow-sm space-y-4">
                <h4 className="text-base font-bold text-gray-900">
                  Verified Publications List ({facultyData.publications.length})
                </h4>

                <div className="divide-y divide-gray-100">
                  {facultyData.publications.map((p, idx) => (
                    <div key={p.id || idx} className="py-3.5 space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="bg-emerald-50 text-emerald-700 font-bold text-[10px] px-2 py-0.5 rounded-full border border-emerald-200">
                          {p.verification_status?.toUpperCase() || 'VERIFIED'}
                        </span>
                        {p.year && <span className="text-xs font-semibold text-gray-500">({p.year})</span>}
                        {p.citation_count > 0 && (
                          <span className="text-xs text-emerald-600 font-medium">
                            • {p.citation_count} Citations
                          </span>
                        )}
                      </div>
                      <h5 className="font-bold text-sm text-gray-900 leading-snug">{p.title}</h5>
                      <div className="text-xs text-gray-500 flex flex-wrap gap-3">
                        {(p.journal_name || p.conference_name) && (
                          <span className="italic">{p.journal_name || p.conference_name}</span>
                        )}
                        {p.doi && (
                          <a
                            href={`https://doi.org/${p.doi.replace(/^https?:\/\/doi\.org\//, '')}`}
                            target="_blank"
                            rel="noreferrer"
                            className="font-mono text-blue-600 hover:underline flex items-center gap-1"
                          >
                            DOI: {p.doi} <ExternalLink size={10} />
                          </a>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* TAB 3: DEPARTMENT REPORT */}
      {activeTab === 'department' && (
        <div className="space-y-5">
          <div className="bg-white p-4 rounded-2xl border border-gray-200 shadow-sm flex items-center gap-3">
            <span className="text-xs font-bold text-gray-600 uppercase tracking-wider">Select Department:</span>
            <select
              value={selectedDept}
              onChange={(e) => setSelectedDept(e.target.value)}
              className="bg-gray-50 border border-gray-200 text-gray-900 font-bold text-xs rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            >
              <option value="CSE">Computer Science & Engineering (CSE)</option>
              <option value="ECE">Electronics & Communication (ECE)</option>
              <option value="IT">Information Technology (IT)</option>
              <option value="MECH">Mechanical Engineering (MECH)</option>
            </select>
          </div>

          {deptData && (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
                <div className="stat-card p-5 bg-white border border-gray-200 rounded-2xl shadow-sm">
                  <p className="text-xs font-bold text-gray-500 uppercase">Department Faculty</p>
                  <h3 className="text-2xl font-black text-gray-900 mt-1">{deptData.summary.total_faculty}</h3>
                </div>
                <div className="stat-card p-5 bg-white border border-gray-200 rounded-2xl shadow-sm">
                  <p className="text-xs font-bold text-gray-500 uppercase">Total Publications</p>
                  <h3 className="text-2xl font-black text-gray-900 mt-1">{deptData.summary.total_publications}</h3>
                </div>
                <div className="stat-card p-5 bg-white border border-emerald-200 rounded-2xl shadow-sm">
                  <p className="text-xs font-bold text-emerald-800 uppercase">Verified Rate</p>
                  <h3 className="text-2xl font-black text-emerald-900 mt-1">{deptData.summary.verification_rate}%</h3>
                </div>
                <div className="stat-card p-5 bg-white border border-blue-200 rounded-2xl shadow-sm">
                  <p className="text-xs font-bold text-blue-800 uppercase">Total Citations</p>
                  <h3 className="text-2xl font-black text-blue-900 mt-1">{deptData.summary.total_citations}</h3>
                </div>
              </div>

              {/* Faculty Ranking in Department */}
              <div className="bg-white p-6 rounded-2xl border border-gray-200 shadow-sm space-y-4">
                <h4 className="text-base font-bold text-gray-900">Faculty Research Performance Ranking</h4>
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead>
                      <tr className="border-b border-gray-200 text-gray-500 font-bold uppercase text-[11px] bg-gray-50/70">
                        <th className="py-3 px-4">Faculty Name</th>
                        <th className="py-3 px-4">Designation</th>
                        <th className="py-3 px-4">Publications</th>
                        <th className="py-3 px-4">Citations</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100 text-gray-700">
                      {deptData.faculty_ranking.map((fac, idx) => (
                        <tr key={fac.id || idx} className="hover:bg-gray-50/80 transition-colors">
                          <td className="py-3 px-4 font-bold text-gray-900">{fac.name}</td>
                          <td className="py-3 px-4 text-gray-600">{fac.designation || 'Faculty'}</td>
                          <td className="py-3 px-4 font-bold text-blue-600">{fac.publication_count}</td>
                          <td className="py-3 px-4 font-bold text-emerald-600">{fac.citation_count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* TAB 4: INSTITUTIONAL REPORT */}
      {activeTab === 'institution' && (
        <div className="space-y-5">
          {instData && (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
                <div className="stat-card p-5 bg-white border border-gray-200 rounded-2xl shadow-sm">
                  <p className="text-xs font-bold text-gray-500 uppercase">Active Faculty</p>
                  <h3 className="text-3xl font-black text-gray-900 mt-1">{instData.kpis.total_faculty}</h3>
                </div>
                <div className="stat-card p-5 bg-white border border-gray-200 rounded-2xl shadow-sm">
                  <p className="text-xs font-bold text-gray-500 uppercase">Total Publications</p>
                  <h3 className="text-3xl font-black text-gray-900 mt-1">{instData.kpis.total_publications}</h3>
                </div>
                <div className="stat-card p-5 bg-white border border-emerald-200 rounded-2xl shadow-sm">
                  <p className="text-xs font-bold text-emerald-800 uppercase">Institutional Verification</p>
                  <h3 className="text-3xl font-black text-emerald-900 mt-1">{instData.kpis.verification_rate}%</h3>
                </div>
                <div className="stat-card p-5 bg-white border border-blue-200 rounded-2xl shadow-sm">
                  <p className="text-xs font-bold text-blue-800 uppercase">Indexed Publications</p>
                  <h3 className="text-3xl font-black text-blue-900 mt-1">
                    {instData.kpis.scopus_indexed_estimate + instData.kpis.scie_indexed_estimate}
                  </h3>
                </div>
              </div>

              {/* Annual Growth Records */}
              <div className="bg-white p-6 rounded-2xl border border-gray-200 shadow-sm space-y-4">
                <h4 className="text-base font-bold text-gray-900">Annual Research Growth Summary</h4>
                <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">
                  {instData.annual_growth.map((g) => (
                    <div key={g.year} className="bg-gray-50 p-3.5 rounded-xl border border-gray-200 text-center">
                      <span className="text-xs font-bold text-gray-500">{g.year}</span>
                      <h5 className="text-xl font-black text-blue-900 mt-1">{g.publications}</h5>
                      <span className="text-[11px] text-gray-400">Papers</span>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
