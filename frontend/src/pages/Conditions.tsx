import { useCallback, useEffect, useState } from 'react'
import { del, get, post, put } from '../api'

const BLANK = { name: '', basis: 'direct', secondary_to: '', onset_date: '',
  exposure: '', notes: '', status: 'selected', sort: 0 }

export default function ConditionsPage({ caseId }: { caseId: number }) {
  const [rows, setRows] = useState<any[]>([])
  const [draft, setDraft] = useState<any>(BLANK)
  const [err, setErr] = useState('')

  const refresh = useCallback(
    () => get(`/api/cases/${caseId}/conditions`).then(setRows), [caseId])
  useEffect(() => { refresh() }, [refresh])

  async function add() {
    if (!draft.name.trim()) return
    setErr('')
    try {
      await post(`/api/cases/${caseId}/conditions`, draft)
      setDraft(BLANK)
      refresh()
    } catch (e: any) { setErr(e.message) }
  }

  const setStatus = (row: any, status: string) =>
    put(`/api/conditions/${row.id}`, { ...row, status }).then(refresh)

  const suggested = rows.filter((r) => r.status === 'suggested')
  const selected = rows.filter((r) => r.status !== 'suggested')

  const basisLabel: any = { direct: 'Direct', secondary: 'Secondary',
    presumptive: 'Presumptive', increase: 'Increase' }

  return (
    <>
      <h2>Conditions</h2>
      <p className="sub">The conditions you select here become the rows of Section V on your
        21-526EZ. AI suggestions come from your own records — accept only what is real and current.</p>

      {suggested.length > 0 && (
        <div className="card">
          <h3>Suggested from your records — review each one</h3>
          <table className="tbl">
            <thead><tr><th>Condition</th><th>Basis</th><th>Evidence note</th><th /></tr></thead>
            <tbody>
              {suggested.map((r) => (
                <tr key={r.id}>
                  <td><b>{r.name}</b></td>
                  <td>{basisLabel[r.basis] ?? r.basis}</td>
                  <td style={{ color: 'var(--muted)' }}>{r.notes}</td>
                  <td style={{ whiteSpace: 'nowrap' }}>
                    <button className="btn" style={{ padding: '4px 10px', marginRight: 6 }}
                      onClick={() => setStatus(r, 'selected')}>accept</button>
                    <button className="btn danger" style={{ padding: '4px 10px' }}
                      onClick={() => del(`/api/conditions/${r.id}`).then(refresh)}>dismiss</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="card">
        <h3>Claimed conditions ({selected.length})</h3>
        {selected.length === 0 && <p style={{ color: 'var(--muted)' }}>None yet — add one below or accept a suggestion.</p>}
        {selected.length > 0 && (
          <table className="tbl">
            <thead><tr><th>#</th><th>Condition</th><th>Basis</th><th>Onset</th><th>Exposure / secondary to</th><th /></tr></thead>
            <tbody>
              {selected.map((r, i) => (
                <tr key={r.id}>
                  <td>{i + 1}</td>
                  <td><b>{r.name}</b>{r.notes && <div style={{ color: 'var(--muted)', fontSize: 12 }}>{r.notes}</div>}</td>
                  <td>{basisLabel[r.basis] ?? r.basis}</td>
                  <td>{r.onset_date ?? ''}</td>
                  <td>{r.basis === 'secondary' ? r.secondary_to : r.exposure}</td>
                  <td><button className="btn danger" style={{ padding: '4px 10px' }}
                    onClick={() => del(`/api/conditions/${r.id}`).then(refresh)}>remove</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card">
        <h3>Add a condition</h3>
        <div className="grid c3">
          <label className="f">Condition name
            <input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })}
              placeholder="e.g. Tinnitus" />
          </label>
          <label className="f">Basis
            <select value={draft.basis} onChange={(e) => setDraft({ ...draft, basis: e.target.value })}>
              <option value="direct">Direct service connection</option>
              <option value="secondary">Secondary to another condition</option>
              <option value="presumptive">Presumptive (exposure/era)</option>
              <option value="increase">Increase of rated condition</option>
            </select>
          </label>
          <label className="f">Approx. onset (YYYY-MM)
            <input value={draft.onset_date ?? ''} onChange={(e) => setDraft({ ...draft, onset_date: e.target.value })}
              placeholder="2012-07" />
          </label>
          {draft.basis === 'secondary' && (
            <label className="f">Secondary to which condition?
              <input value={draft.secondary_to ?? ''} onChange={(e) => setDraft({ ...draft, secondary_to: e.target.value })}
                placeholder="e.g. PTSD" />
            </label>
          )}
          {draft.basis !== 'secondary' && (
            <label className="f">Exposure / in-service event (optional)
              <input value={draft.exposure ?? ''} onChange={(e) => setDraft({ ...draft, exposure: e.target.value })}
                placeholder="e.g. burn pits, weapons noise" />
            </label>
          )}
          <label className="f">Notes for the form (optional)
            <input value={draft.notes} onChange={(e) => setDraft({ ...draft, notes: e.target.value })} />
          </label>
        </div>
        <button className="btn" style={{ marginTop: 12 }} onClick={add}>Add condition</button>
        {err && <div className="err">{err}</div>}
      </div>
    </>
  )
}
