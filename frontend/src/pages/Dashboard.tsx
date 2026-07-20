import { useEffect, useState } from 'react'
import { get, getToken, post, setToken } from '../api'
import type { Tab } from '../App'

export default function Dashboard({ caseId, go }: { caseId: number; go: (t: Tab) => void }) {
  const [summary, setSummary] = useState<any>(null)
  const [jobs, setJobs] = useState<any[]>([])
  const [authOn, setAuthOn] = useState<boolean | null>(null)
  const [pass, setPass] = useState('')
  const [note, setNote] = useState('')

  useEffect(() => {
    get('/api/cases').then((cs) => setSummary(cs.find((c: any) => c.id === caseId)))
    get('/api/jobs').then(setJobs)
    get('/api/auth/status').then((s) => setAuthOn(s.enabled))
  }, [caseId])

  async function enableAuth() {
    setNote('')
    try {
      const { token } = await post('/api/auth/setup', { passphrase: pass })
      setToken(token)
      setAuthOn(true)
      setPass('')
      setNote('Passphrase set — the app now locks on every new browser session.')
    } catch (e: any) { setNote(e.message) }
  }

  async function backup() {
    const r = await fetch('/api/backup', {
      method: 'POST',
      headers: getToken() ? { 'X-Auth-Token': getToken() } : undefined,
    })
    const blob = await r.blob()
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = /filename="?([^";]+)"?/.exec(
      r.headers.get('Content-Disposition') ?? '')?.[1] ?? 'backup.zip'
    a.click()
    URL.revokeObjectURL(a.href)
  }

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
      <div className="card">
        <h3>Security & backup</h3>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          {authOn === false && (
            <>
              <label className="f" style={{ minWidth: 220 }}>Set a passphrase (locks the app)
                <input type="password" value={pass} onChange={(e) => setPass(e.target.value)}
                  placeholder="8+ characters" />
              </label>
              <button className="btn ghost" disabled={pass.length < 8}
                onClick={enableAuth}>Enable lock</button>
            </>
          )}
          {authOn && <span className="pill ready">passphrase lock enabled</span>}
          <button className="btn ghost" onClick={backup}>⬇ Download full backup (ZIP)</button>
        </div>
        <p style={{ color: 'var(--muted)', fontSize: 12.5, marginBottom: 0 }}>
          Your records live only in this machine's <code>data/</code> folder. For at-rest
          encryption use OS disk encryption (BitLocker / FileVault / LUKS). Store backups
          somewhere encrypted too.</p>
        {note && <div className="ok">{note}</div>}
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
