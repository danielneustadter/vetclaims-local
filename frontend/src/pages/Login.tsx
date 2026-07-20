import { useState } from 'react'
import { post, setToken } from '../api'

export default function Login({ onDone }: { onDone: () => void }) {
  const [pass, setPass] = useState('')
  const [err, setErr] = useState('')

  async function submit(e: any) {
    e.preventDefault()
    setErr('')
    try {
      const { token } = await post('/api/auth/login', { passphrase: pass })
      setToken(token)
      onDone()
    } catch (e: any) { setErr(e.message) }
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center',
                  minHeight: '70vh' }}>
      <form onSubmit={submit} className="card" style={{ width: 380 }}>
        <h3>🔒 VetClaims Local is locked</h3>
        <label className="f">Passphrase
          <input type="password" autoFocus value={pass}
            onChange={(e) => setPass(e.target.value)} />
        </label>
        <button className="btn" style={{ marginTop: 12 }} type="submit">Unlock</button>
        {err && <div className="err">{err}</div>}
        <p style={{ color: 'var(--muted)', fontSize: 12, marginBottom: 0 }}>
          Forgot it? Delete <code>data/auth.json</code> on this machine to reset
          (your case data is untouched).</p>
      </form>
    </div>
  )
}
