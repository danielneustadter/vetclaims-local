import { useEffect, useState } from 'react'
import { downloadPdf, get } from '../api'

export default function FormsPage({ caseId }: { caseId: number }) {
  const [nConditions, setN] = useState(0)
  const [statement, setStatement] = useState('')
  const [stmtDrafts, setStmtDrafts] = useState<any[]>([])
  const [label, setLabel] = useState('statement')
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')

  useEffect(() => {
    get(`/api/cases/${caseId}/conditions`)
      .then((rows) => setN(rows.filter((r: any) => r.status !== 'suggested').length))
    get(`/api/cases/${caseId}/drafts`)
      .then((rows) => setStmtDrafts(rows.filter((d: any) => d.kind === 'personal_statement')))
  }, [caseId])

  async function dl(url: string, body?: unknown) {
    setErr(''); setMsg('')
    try { setMsg(`Downloaded ${await downloadPdf(url, body)} — open it and review every field.`) }
    catch (e: any) { setErr(e.message) }
  }

  return (
    <>
      <h2>Claim forms</h2>
      <p className="sub">Generated from your profile and selected conditions. Each PDF is a
        draft: open it, verify every field, sign it, and file it yourself on VA.gov.</p>

      <div className="card">
        <h3>VA Form 21-0966 — Intent to File</h3>
        <p style={{ color: 'var(--muted)', fontSize: 13.5 }}>
          File this first. It locks in your effective date and gives you up to one year to
          complete the full claim.</p>
        <button className="btn" onClick={() => dl(`/api/cases/${caseId}/forms/21-0966`)}>
          Generate 21-0966</button>
      </div>

      <div className="card">
        <h3>VA Form 21-526EZ — Application for Disability Compensation</h3>
        <p style={{ color: 'var(--muted)', fontSize: 13.5 }}>
          The main claim form. Your {nConditions} selected condition{nConditions === 1 ? '' : 's'} fill
          Section V. Sign in Section IX before filing.</p>
        <button className="btn" disabled={nConditions === 0}
          onClick={() => dl(`/api/cases/${caseId}/forms/21-526EZ`)}>
          Generate 21-526EZ</button>
        {nConditions === 0 &&
          <div className="err">Select at least one condition first (Conditions tab).</div>}
      </div>

      <div className="card">
        <h3>VA Form 21-4138 — Statement in Support of Claim</h3>
        <p style={{ color: 'var(--muted)', fontSize: 13.5 }}>
          Write a statement or load one of your reviewed drafts; it is placed into the Remarks
          box with your identity block filled.</p>
        {stmtDrafts.length > 0 && (
          <label className="f" style={{ marginBottom: 10 }}>Load a reviewed draft
            <select defaultValue="" onChange={(e) => {
              const d = stmtDrafts.find((x) => x.id === Number(e.target.value))
              if (d) {
                setStatement(d.content)
                setLabel(d.title.replace(/^Personal statement — /, '').slice(0, 30))
              }
            }}>
              <option value="" disabled>choose a draft…</option>
              {stmtDrafts.map((d) => <option key={d.id} value={d.id}>{d.title}</option>)}
            </select>
          </label>
        )}
        <label className="f">Statement text
          <textarea rows={7} value={statement} onChange={(e) => setStatement(e.target.value)}
            placeholder="In my own words…" />
        </label>
        <button className="btn" style={{ marginTop: 10 }} disabled={!statement.trim()}
          onClick={() => dl(`/api/cases/${caseId}/forms/21-4138`, { statement, label })}>
          Generate 21-4138</button>
      </div>

      {msg && <div className="ok">{msg}</div>}
      {err && <div className="err">{err}</div>}
    </>
  )
}
