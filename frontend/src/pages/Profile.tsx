import { useEffect, useState } from 'react'
import { get, pollJob, post, put } from '../api'

const empty = {
  claim_process: 'FDC',
  identity: { first_name: '', middle_initial: '', last_name: '', ssn: '',
    va_file_number: '', date_of_birth: '', service_number: '' },
  contact: { phone: '', email: '', street: '', apt: '', city: '', state: '',
    country: 'US', zip_code: '' },
  service: { periods: [], served_under_other_name: false, other_name: '',
    pow: false, combat_service: false, exposures: [] },
  direct_deposit: { account_type: '', bank_name: '', routing_number: '', account_number: '' },
}

export default function ProfilePage({ caseId }: { caseId: number }) {
  const [p, setP] = useState<any>(empty)
  const [busy, setBusy] = useState('')
  const [note, setNote] = useState('')
  const [err, setErr] = useState('')

  useEffect(() => { get(`/api/cases/${caseId}/profile`).then(setP) }, [caseId])

  const set = (section: string, field: string) => (e: any) =>
    setP({ ...p, [section]: { ...p[section], [field]: e.target.value } })

  const setPeriod = (i: number, field: string) => (e: any) => {
    const periods = [...p.service.periods]
    periods[i] = { ...periods[i], [field]: e.target.value }
    setP({ ...p, service: { ...p.service, periods } })
  }

  async function save() {
    setErr(''); setNote('')
    try { await put(`/api/cases/${caseId}/profile`, p); setNote('Saved.') }
    catch (e: any) { setErr(e.message) }
  }

  async function prefill() {
    setErr(''); setNote(''); setBusy('Queued…')
    try {
      const { job_id } = await post(`/api/cases/${caseId}/profile/prefill`)
      const job = await pollJob(job_id, setBusy)
      setP(await get(`/api/cases/${caseId}/profile`))
      setNote(`Pre-fill done: analyzed ${job.result.documents_analyzed} document(s), ` +
        `suggested ${job.result.conditions_suggested} condition(s) — see the Conditions tab. ` +
        'Review every field below.')
    } catch (e: any) { setErr(e.message) }
    setBusy('')
  }

  const f = (label: string, section: string, field: string, props: any = {}) => (
    <label className="f">{label}
      <input value={p[section]?.[field] ?? ''} onChange={set(section, field)} {...props} />
    </label>
  )

  return (
    <>
      <h2>Claimant profile</h2>
      <p className="sub">These fields flow directly onto your forms. Pre-fill reads your uploaded
        documents and fills gaps only — it never overwrites what you typed. Review everything.</p>

      <div style={{ display: 'flex', gap: 10, marginBottom: 16 }}>
        <button className="btn gold" onClick={prefill} disabled={!!busy}>
          ✨ Pre-fill from my documents</button>
        <button className="btn" onClick={save}>Save profile</button>
        {busy && <span className="progress">{busy}</span>}
      </div>
      {note && <div className="ok">{note}</div>}
      {err && <div className="err">{err}</div>}

      <div className="card">
        <h3>Identity</h3>
        <div className="grid c3">
          {f('First name', 'identity', 'first_name')}
          {f('Middle initial', 'identity', 'middle_initial', { maxLength: 1 })}
          {f('Last name', 'identity', 'last_name')}
          {f('Social Security Number', 'identity', 'ssn', { placeholder: '###-##-####' })}
          {f('VA file number (if any)', 'identity', 'va_file_number')}
          {f('Date of birth', 'identity', 'date_of_birth', { type: 'date' })}
        </div>
      </div>

      <div className="card">
        <h3>Contact</h3>
        <div className="grid c3">
          {f('Phone', 'contact', 'phone')}
          {f('Email', 'contact', 'email')}
          {f('Street', 'contact', 'street')}
          {f('Apt/Unit', 'contact', 'apt')}
          {f('City', 'contact', 'city')}
          {f('State', 'contact', 'state', { maxLength: 2 })}
          {f('ZIP', 'contact', 'zip_code')}
          {f('Country', 'contact', 'country', { maxLength: 2 })}
        </div>
      </div>

      <div className="card">
        <h3>Military service</h3>
        {(p.service.periods.length ? p.service.periods : [{ branch: '', entry_date: '', separation_date: '' }])
          .map((sp: any, i: number) => (
          <div className="grid c3" key={i} style={{ marginBottom: 8 }}>
            <label className="f">Branch
              <input value={sp.branch ?? ''} onChange={setPeriod(i, 'branch')} placeholder="Army, Navy…" />
            </label>
            <label className="f">Entry date
              <input type="date" value={sp.entry_date ?? ''} onChange={setPeriod(i, 'entry_date')} />
            </label>
            <label className="f">Separation date
              <input type="date" value={sp.separation_date ?? ''} onChange={setPeriod(i, 'separation_date')} />
            </label>
          </div>
        ))}
        {p.service.periods.length === 0 && (
          <button className="btn ghost" onClick={() =>
            setP({ ...p, service: { ...p.service, periods: [{ branch: '', entry_date: '', separation_date: '', service_component: 'Active', character_of_discharge: '' }] } })}>
            + add service period</button>
        )}
        <label className="f" style={{ marginTop: 10 }}>Toxic exposures (comma-separated: burn pits, asbestos, radiation…)
          <input value={(p.service.exposures ?? []).join(', ')}
            onChange={(e) => setP({ ...p, service: { ...p.service, exposures: e.target.value.split(',').map((s: string) => s.trim()).filter(Boolean) } })} />
        </label>
      </div>

      <div className="card">
        <h3>Claim process & payment</h3>
        <div className="grid c3">
          <label className="f">Claim process
            <select value={p.claim_process} onChange={(e) => setP({ ...p, claim_process: e.target.value })}>
              <option value="FDC">Fully Developed Claim (faster)</option>
              <option value="Standard">Standard claim process</option>
            </select>
          </label>
          {f('Bank name (optional)', 'direct_deposit', 'bank_name')}
          {f('Routing number (optional)', 'direct_deposit', 'routing_number')}
          {f('Account number (optional)', 'direct_deposit', 'account_number')}
        </div>
        <p style={{ color: 'var(--muted)', fontSize: 12.5, marginBottom: 0 }}>
          Direct deposit is optional here — you can leave it blank and provide it to the VA
          separately. It is stored only in your local database.</p>
      </div>

      <button className="btn" onClick={save}>Save profile</button>
    </>
  )
}
