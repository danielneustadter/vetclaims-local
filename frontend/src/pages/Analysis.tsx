import { useCallback, useEffect, useState } from 'react'
import { get, post } from '../api'

function Citations({ list }: { list: any[] }) {
  if (!list?.length) return null
  return (
    <ul style={{ margin: '6px 0 0', paddingLeft: 18, fontSize: 12.5 }}>
      {list.map((c, i) => (
        <li key={i} style={{ marginBottom: 2 }}>
          <span>{c.detail}</span>
          <span style={{ color: 'var(--muted)' }}> — {c.filename} p.{c.page_no}{c.date ? `, ${c.date}` : ''}</span>
        </li>
      ))}
    </ul>
  )
}

function Projection({ rating }: { rating: any }) {
  if (!rating) return <span style={{ color: 'var(--muted)', fontSize: 12.5 }}>
    No diagnostic-code match — rating impact unknown.</span>
  return (
    <div style={{ fontSize: 12.5 }}>
      <div style={{ color: 'var(--muted)' }}>
        DC {rating.diagnostic_code} — {rating.schedule_name}
        {rating.tiers.length > 0 && <> · tiers: {rating.tiers.map((t: number) => `${t}%`).join(' / ')}</>}
      </div>
      {rating.projections.map((p: any) => (
        <div key={p.at_percent}>
          If rated <b>{p.at_percent}%</b>: combined {p.before}% → <b>{p.after}%</b>
          {p.delta > 0 ? ` (+${p.delta})` : ' (no change — VA math combines, not adds)'}
        </div>
      ))}
    </div>
  )
}

export default function AnalysisPage({ caseId }: { caseId: number }) {
  const [a, setA] = useState<any>(null)
  const [err, setErr] = useState('')
  const [added, setAdded] = useState<Set<string>>(new Set())

  const refresh = useCallback(
    () => get(`/api/cases/${caseId}/analysis`).then(setA).catch((e) => setErr(e.message)),
    [caseId])
  useEffect(() => { refresh() }, [refresh])

  async function accept(s: any) {
    try {
      await post(`/api/cases/${caseId}/conditions`, {
        name: s.name, basis: s.basis, secondary_to: s.secondary_to ?? null,
        exposure: s.exposure ?? null, notes: s.why?.slice(0, 200) ?? '',
        status: 'selected', sort: 50,
      })
      setAdded(new Set([...added, s.name]))
      refresh()
    } catch (e: any) { setErr(e.message) }
  }

  if (!a) return <><h2>Analysis</h2><p className="sub">Loading…</p></>

  const card = (s: any, extra?: string) => (
    <div key={s.name} style={{ borderTop: '1px solid var(--line)', padding: '12px 0' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
        <div style={{ flex: 1 }}>
          <b>{s.name}</b>
          {extra && <span style={{ color: 'var(--muted)', fontSize: 12.5 }}> · {extra}</span>}
          <div style={{ fontSize: 13, margin: '4px 0' }}>{s.why}</div>
          <Citations list={s.citations} />
          <div style={{ margin: '6px 0' }}><Projection rating={s.rating} /></div>
          {s.gaps?.length > 0 && (
            <ul style={{ margin: '4px 0 0', paddingLeft: 18, fontSize: 12.5, color: '#8a6d1a' }}>
              {s.gaps.map((g: string, i: number) => <li key={i}>{g}</li>)}
            </ul>
          )}
        </div>
        <div>
          {added.has(s.name)
            ? <span className="pill selected">added</span>
            : <button className="btn" style={{ padding: '5px 12px' }}
                onClick={() => accept(s)}>add to claim</button>}
        </div>
      </div>
    </div>
  )

  return (
    <>
      <h2>Analysis</h2>
      <p className="sub">Deterministic analysis of your case file: documented but unclaimed
        conditions, secondary-connection candidates, presumptive eligibility, and what each
        claim could do to your combined rating. Everything cites your own records — and
        everything needs your judgment and a doctor's opinion, not just this screen.</p>
      {err && <div className="err">{err}</div>}

      <div className="grid c2">
        <div className="card stat">
          <div className="n">{a.current_combined}%</div>
          <div className="l">current combined rating (§4.25/§4.26)</div>
        </div>
        <div className="card">
          <h3>Existing ratings</h3>
          {a.existing_ratings.length === 0 && <span style={{ color: 'var(--muted)' }}>none on record</span>}
          {a.existing_ratings.map((r: any) => (
            <div key={r.condition} style={{ fontSize: 13.5 }}>
              <b>{r.percent}%</b> {r.condition} {r.diagnostic_code && <span style={{ color: 'var(--muted)' }}>(DC {r.diagnostic_code})</span>}
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <h3>Documented in your records, not yet claimed ({a.direct_suggestions.length})</h3>
        {a.direct_suggestions.length === 0 && <p style={{ color: 'var(--muted)' }}>
          Nothing found — build the case file first (Case File tab).</p>}
        {a.direct_suggestions.map((s: any) => card(s))}
      </div>

      <div className="card">
        <h3>Secondary-connection candidates ({a.secondary_suggestions.length})</h3>
        <p style={{ color: 'var(--muted)', fontSize: 12.5 }}>
          Medically recognized consequences of your rated/claimed conditions. Only pursue ones
          you actually have; each needs a current diagnosis and a physician's nexus opinion.</p>
        {a.secondary_suggestions.map((s: any) => card(s, `secondary to ${s.secondary_to}`))}
      </div>

      {a.presumptive_eligibility.length > 0 && (
        <div className="card">
          <h3>Presumptive eligibility</h3>
          {a.presumptive_eligibility.map((p: any) => (
            <div key={p.category} style={{ marginBottom: 10 }}>
              <b>{p.category}</b>
              <div style={{ fontSize: 12.5, color: 'var(--muted)' }}>{p.eligibility}</div>
              {p.documented_matches.length > 0 ? (
                <div style={{ fontSize: 13 }}>
                  Documented matches in your records:
                  {p.documented_matches.map((m: any) => (
                    <div key={m.name} style={{ marginTop: 4 }}>
                      <b>{m.name}</b>
                      <Citations list={m.citations} />
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ fontSize: 12.5, color: 'var(--muted)' }}>
                  No matching conditions documented in your records yet.</div>
              )}
            </div>
          ))}
        </div>
      )}
    </>
  )
}
