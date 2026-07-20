import { useCallback, useEffect, useState } from 'react'
import { downloadPdf, get, pollJob, post } from '../api'

export default function AppealsPage({ caseId }: { caseId: number }) {
  const [docs, setDocs] = useState<any[]>([])
  const [decision, setDecision] = useState<any>({ issues: [], recommendations: [] })
  const [busy, setBusy] = useState('')
  const [err, setErr] = useState('')
  const [msg, setMsg] = useState('')

  const refresh = useCallback(async () => {
    setDocs((await get(`/api/cases/${caseId}`)).documents)
    setDecision(await get(`/api/cases/${caseId}/decision`))
  }, [caseId])
  useEffect(() => { refresh() }, [refresh])

  async function parse(docId: number) {
    setErr(''); setBusy('Parsing decision letter…')
    try {
      const { job_id } = await post(`/api/documents/${docId}/parse-decision`)
      await pollJob(job_id, setBusy)
      await refresh()
    } catch (e: any) { setErr(e.message) }
    setBusy('')
  }

  async function appeal(form: string, issueIds: number[]) {
    setErr(''); setMsg('')
    try {
      const name = await downloadPdf(`/api/cases/${caseId}/appeals/${form}`,
        { issue_ids: issueIds })
      setMsg(`Downloaded ${name} — review, sign, and file it yourself.`)
    } catch (e: any) { setErr(e.message) }
  }

  async function rebuttal(issueId: number) {
    setErr(''); setBusy('Drafting rebuttal from your records…')
    try {
      const { job_id } = await post(`/api/cases/${caseId}/rebuttal`, { issue_id: issueId })
      await pollJob(job_id, setBusy)
      setMsg('Rebuttal draft created — review it in the Drafts tab (grounding-checked).')
    } catch (e: any) { setErr(e.message) }
    setBusy('')
  }

  const outcomePill: any = { granted: 'ready', denied: 'error', deferred: 'suggested' }

  return (
    <>
      <h2>Decision & appeals</h2>
      <p className="sub">Upload your VA decision letter on the Documents tab, then parse it here.
        You get each issue's outcome and reason, the recommended AMA review lane, deadlines, and
        drafted appeal forms — all for your review and signature.</p>

      <div className="card">
        <h3>Parse a decision letter</h3>
        {docs.length === 0 && <p style={{ color: 'var(--muted)' }}>No documents uploaded.</p>}
        {docs.map((d) => (
          <div key={d.id} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0' }}>
            <span>{d.filename} <span style={{ color: 'var(--muted)' }}>({d.doc_type})</span></span>
            <button className="btn ghost" style={{ padding: '3px 12px' }} disabled={!!busy}
              onClick={() => parse(d.id)}>parse as decision</button>
          </div>
        ))}
        {busy && <div className="progress">{busy}</div>}
      </div>

      {decision.issues.length > 0 && (
        <div className="card">
          <h3>Decided issues</h3>
          <table className="tbl">
            <thead><tr><th>Condition</th><th>Outcome</th><th>%</th><th>Reason</th></tr></thead>
            <tbody>
              {decision.issues.map((i: any) => (
                <tr key={i.id}>
                  <td><b>{i.condition}</b></td>
                  <td><span className={`pill ${outcomePill[i.outcome]}`}>{i.outcome}</span></td>
                  <td>{i.percent ? `${i.percent}%` : '—'}</td>
                  <td style={{ color: 'var(--muted)' }}>{i.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {decision.recommendations.map((r: any) => (
        <div className="card" key={r.issue_id}>
          <h3>{r.condition} — recommended: {r.lane === 'hlr' ? 'Higher-Level Review' : 'Supplemental Claim'} ({r.form})</h3>
          <p style={{ fontSize: 13.5 }}>{r.why}</p>
          <p style={{ fontSize: 12.5, color: r.deadline ? 'var(--bad)' : 'var(--muted)' }}>
            {r.deadline ? `Deadline: ${r.deadline}. ` : ''}{r.deadline_note}</p>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button className="btn" onClick={() => appeal(r.form, [r.issue_id])}>
              Generate {r.form}</button>
            <button className="btn ghost" disabled={!!busy}
              onClick={() => rebuttal(r.issue_id)}>✍️ Draft rebuttal statement</button>
          </div>
          <p style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 0 }}>
            Prefer a Board appeal instead? Complete VA Form 10182 at va.gov/board-appeals.</p>
        </div>
      ))}

      {msg && <div className="ok">{msg}</div>}
      {err && <div className="err">{err}</div>}
    </>
  )
}
