import { useCallback, useEffect, useState } from 'react'
import { del, get, pollJob, post, put } from '../api'

const KINDS = [
  ['personal_statement', '✍️ Personal statement', 'AI-drafted from your records, grounding-checked'],
  ['nexus_outline', '🩺 Nexus outline', 'for your physician'],
  ['cp_prep', '📋 C&P prep', 'exam preparation sheet'],
  ['lay_template', '👥 Lay statement', 'template for a witness'],
] as const

export default function DraftsPage({ caseId }: { caseId: number }) {
  const [conditions, setConditions] = useState<any[]>([])
  const [drafts, setDrafts] = useState<any[]>([])
  const [open, setOpen] = useState<number | null>(null)
  const [busy, setBusy] = useState('')
  const [err, setErr] = useState('')
  const [saved, setSaved] = useState(0)

  const refresh = useCallback(async () => {
    setConditions((await get(`/api/cases/${caseId}/conditions`))
      .filter((c: any) => c.status !== 'suggested'))
    setDrafts(await get(`/api/cases/${caseId}/drafts`))
  }, [caseId])
  useEffect(() => { refresh() }, [refresh])

  async function generate(conditionId: number, kind: string) {
    setErr('')
    try {
      const r = await post(`/api/cases/${caseId}/drafts`, { condition_id: conditionId, kind })
      if (r.job_id) {
        setBusy('Drafting from your records…')
        await pollJob(r.job_id, setBusy)
        setBusy('')
      }
      await refresh()
      const latest = (await get(`/api/cases/${caseId}/drafts`))[0]
      setOpen(latest?.id ?? null)
    } catch (e: any) { setErr(e.message); setBusy('') }
  }

  async function save(d: any) {
    await put(`/api/drafts/${d.id}`, { content: d.content })
    setSaved(d.id)
    setTimeout(() => setSaved(0), 1500)
  }

  return (
    <>
      <h2>Drafts</h2>
      <p className="sub">Statements, nexus outlines, C&P prep sheets, and lay-statement templates
        per claimed condition. Personal statements are AI drafts checked against your records —
        anything the checker could not verify is flagged. Edit everything before use.</p>

      {conditions.length === 0 && <div className="card">
        <p style={{ color: 'var(--muted)', margin: 0 }}>Select conditions first (Conditions or Analysis tab).</p></div>}

      {conditions.map((c) => (
        <div className="card" key={c.id}>
          <h3>{c.name}</h3>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {KINDS.map(([kind, label, hint]) => (
              <button key={kind} className="btn ghost" disabled={!!busy}
                title={hint} onClick={() => generate(c.id, kind)}>{label}</button>
            ))}
          </div>
        </div>
      ))}
      {busy && <div className="progress">{busy}</div>}
      {err && <div className="err">{err}</div>}

      {drafts.length > 0 && <h3 style={{ margin: '18px 0 8px' }}>Your drafts</h3>}
      {drafts.map((d) => (
        <div className="card" key={d.id}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <b style={{ cursor: 'pointer' }} onClick={() => setOpen(open === d.id ? null : d.id)}>
              {open === d.id ? '▾' : '▸'} {d.title}</b>
            <div style={{ display: 'flex', gap: 8 }}>
              {d.grounding?.checked && (d.grounding.unsupported?.length
                ? <span className="pill error">{d.grounding.unsupported.length} unverified claim(s)</span>
                : <span className="pill ready">grounding ✓</span>)}
              <button className="btn danger" style={{ padding: '3px 10px' }}
                onClick={() => del(`/api/drafts/${d.id}`).then(refresh)}>delete</button>
            </div>
          </div>
          {open === d.id && (
            <>
              {d.grounding?.unsupported?.length > 0 && (
                <div className="err" style={{ margin: '8px 0' }}>
                  The checker could not verify these sentences against your records — edit or
                  delete them unless you know them to be true:
                  <ul style={{ margin: '4px 0 0', paddingLeft: 18 }}>
                    {d.grounding.unsupported.map((s: string, i: number) => <li key={i}>{s}</li>)}
                  </ul>
                </div>
              )}
              <textarea
                style={{ width: '100%', minHeight: 320, marginTop: 10, fontFamily: 'inherit',
                         fontSize: 13.5, border: '1px solid var(--line)', borderRadius: 6, padding: 10 }}
                value={d.content}
                onChange={(e) => setDrafts(drafts.map((x) =>
                  x.id === d.id ? { ...x, content: e.target.value } : x))}
              />
              <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                <button className="btn" onClick={() => save(d)}>Save</button>
                {saved === d.id && <span className="ok">Saved.</span>}
                {d.kind === 'personal_statement' && (
                  <span style={{ color: 'var(--muted)', fontSize: 12.5, alignSelf: 'center' }}>
                    Use it from the Claim Forms tab → 21-4138.</span>
                )}
              </div>
            </>
          )}
        </div>
      ))}
    </>
  )
}
