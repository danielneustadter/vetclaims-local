import { useEffect, useState } from 'react'
import { get } from '../api'
import type { Tab } from '../App'

export default function Dashboard({ caseId, go }: { caseId: number; go: (t: Tab) => void }) {
  const [summary, setSummary] = useState<any>(null)
  const [jobs, setJobs] = useState<any[]>([])

  useEffect(() => {
    get('/api/cases').then((cs) => setSummary(cs.find((c: any) => c.id === caseId)))
    get('/api/jobs').then(setJobs)
  }, [caseId])

  const steps = [
    ['1. Upload records', 'DD-214, service treatment records, VA decisions, private medical records.', 'documents'],
    ['2. Review your profile', 'Let the AI pre-fill your identity and service details, then correct them.', 'profile'],
    ['3. Pick your conditions', 'Review suggested conditions and select what you intend to claim.', 'conditions'],
    ['4. Generate your forms', 'Download the filled 21-526EZ, statements, and Intent to File.', 'forms'],
  ] as const

  return (
    <>
      <h2>Dashboard</h2>
      <p className="sub">Everything runs on this machine — your records never leave it.</p>
      <div className="grid c3">
        <div className="card stat"><div className="n">{summary?.documents ?? 0}</div><div className="l">documents uploaded</div></div>
        <div className="card stat"><div className="n">{summary?.conditions ?? 0}</div><div className="l">conditions selected</div></div>
        <div className="card stat"><div className="n">{summary?.suggested ?? 0}</div><div className="l">AI-suggested to review</div></div>
      </div>
      <div className="card">
        <h3>How it works</h3>
        {steps.map(([title, desc, tab]) => (
          <p key={title} style={{ margin: '10px 0' }}>
            <a href="#" onClick={(e) => { e.preventDefault(); go(tab) }}
               style={{ fontWeight: 600 }}>{title}</a>
            <span style={{ color: 'var(--muted)' }}> — {desc}</span>
          </p>
        ))}
      </div>
      {jobs.length > 0 && (
        <div className="card">
          <h3>Recent activity</h3>
          <table className="tbl">
            <thead><tr><th>Job</th><th>Status</th><th>Detail</th></tr></thead>
            <tbody>
              {jobs.slice(0, 6).map((j) => (
                <tr key={j.id}>
                  <td>{j.type}</td>
                  <td><span className={`pill ${j.status === 'done' ? 'ready' : j.status === 'error' ? 'error' : 'extracting'}`}>{j.status}</span></td>
                  <td style={{ color: 'var(--muted)' }}>{j.error ?? j.progress ?? ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
