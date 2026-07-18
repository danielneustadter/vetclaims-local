import { useCallback, useEffect, useState } from 'react'
import { get, pollJob, post } from '../api'

const KIND_COLOR: Record<string, string> = {
  diagnosis: 'ready', injury: 'error', complaint: 'suggested',
  treatment: 'extracting', exposure: 'error', referral: 'extracting',
}

export default function CaseFilePage({ caseId }: { caseId: number }) {
  const [groups, setGroups] = useState<any[]>([])
  const [ratings, setRatings] = useState<any[]>([])
  const [busy, setBusy] = useState('')
  const [err, setErr] = useState('')
  const [q, setQ] = useState('')
  const [hits, setHits] = useState<any[]>([])

  const refresh = useCallback(() => {
    get(`/api/cases/${caseId}/timeline`).then(setGroups)
    get(`/api/cases/${caseId}/ratings`).then(setRatings)
  }, [caseId])
  useEffect(() => { refresh() }, [refresh])

  async function extract() {
    setErr(''); setBusy('Queued…')
    try {
      const { job_id } = await post(`/api/cases/${caseId}/extract`)
      await pollJob(job_id, setBusy)
      refresh()
    } catch (e: any) { setErr(e.message) }
    setBusy('')
  }

  async function search(e: any) {
    e.preventDefault()
    if (q.trim().length < 2) return
    setHits(await get(`/api/cases/${caseId}/search?q=${encodeURIComponent(q)}`))
  }

  return (
    <>
      <h2>Case file</h2>
      <p className="sub">Every clinical fact extracted from your records, grouped by condition,
        each with a citation back to the exact document and page.</p>

      <div style={{ display: 'flex', gap: 10, marginBottom: 16 }}>
        <button className="btn gold" onClick={extract} disabled={!!busy}>
          🔍 Build / rebuild case file</button>
        {busy && <span className="progress">{busy}</span>}
      </div>
      {err && <div className="err">{err}</div>}

      {ratings.length > 0 && (
        <div className="card">
          <h3>Existing VA ratings</h3>
          <table className="tbl">
            <thead><tr><th>Condition</th><th>%</th><th>Diagnostic code</th><th>Effective</th></tr></thead>
            <tbody>{ratings.map((r) => (
              <tr key={r.id}><td>{r.condition}</td><td><b>{r.percent}%</b></td>
                <td>{r.diagnostic_code}</td><td>{r.effective_date}</td></tr>))}
            </tbody>
          </table>
        </div>
      )}

      {groups.map((g) => (
        <div className="card" key={g.condition}>
          <h3>{g.condition}</h3>
          <table className="tbl">
            <thead><tr><th>Date</th><th>Type</th><th>Record</th><th>Source</th></tr></thead>
            <tbody>
              {g.events.map((e: any) => (
                <tr key={e.id}>
                  <td style={{ whiteSpace: 'nowrap' }}>{e.date ?? '—'}</td>
                  <td><span className={`pill ${KIND_COLOR[e.kind] ?? 'extracting'}`}>{e.kind}</span></td>
                  <td>{e.detail}{e.provider && <span style={{ color: 'var(--muted)' }}> — {e.provider}</span>}</td>
                  <td style={{ color: 'var(--muted)', whiteSpace: 'nowrap' }}>{e.filename} p.{e.page_no}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
      {groups.length === 0 && !busy && (
        <div className="card"><p style={{ color: 'var(--muted)', margin: 0 }}>
          No case file yet — upload documents, then build the case file.</p></div>
      )}

      <div className="card">
        <h3>Search your records</h3>
        <form onSubmit={search} style={{ display: 'flex', gap: 10 }}>
          <input style={{ flex: 1, border: '1px solid var(--line)', borderRadius: 6, padding: '8px 10px' }}
            value={q} onChange={(e) => setQ(e.target.value)}
            placeholder="e.g. knee pain after PT" />
          <button className="btn" type="submit">Search</button>
        </form>
        {hits.map((h) => (
          <div key={h.chunk_id} style={{ borderTop: '1px solid var(--line)', paddingTop: 10, marginTop: 10 }}>
            <div style={{ color: 'var(--muted)', fontSize: 12 }}>
              {h.filename} p.{h.page_start}{h.page_end !== h.page_start ? `–${h.page_end}` : ''}</div>
            <div style={{ fontSize: 13 }}>{h.text.slice(0, 400)}…</div>
          </div>
        ))}
      </div>
    </>
  )
}
