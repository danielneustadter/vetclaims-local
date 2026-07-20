import { useCallback, useEffect, useRef, useState } from 'react'
import { del, get, getToken, pollJob, post } from '../api'

export default function DocumentsPage({ caseId }: { caseId: number }) {
  const [docs, setDocs] = useState<any[]>([])
  const [drag, setDrag] = useState(false)
  const [busy, setBusy] = useState('')
  const [err, setErr] = useState('')
  const fileInput = useRef<HTMLInputElement>(null)

  const refresh = useCallback(
    () => get(`/api/cases/${caseId}`).then((c) => setDocs(c.documents)),
    [caseId])
  useEffect(() => { refresh() }, [refresh])

  async function upload(files: FileList | null) {
    if (!files?.length) return
    setErr('')
    for (const file of Array.from(files)) {
      setBusy(`Uploading ${file.name}…`)
      const fd = new FormData()
      fd.append('file', file)
      try {
        const r = await fetch(`/api/cases/${caseId}/documents`, {
          method: 'POST', body: fd,
          headers: getToken() ? { 'X-Auth-Token': getToken() } : undefined,
        })
        if (!r.ok) throw new Error((await r.json()).detail ?? r.statusText)
        const { job_id } = await r.json()
        await refresh()
        setBusy(`Extracting text from ${file.name}…`)
        await pollJob(job_id, (p) => setBusy(`Extracting ${file.name}: ${p}`))
      } catch (e: any) {
        setErr(`${file.name}: ${e.message}`)
      }
    }
    setBusy('')
    refresh()
  }

  return (
    <>
      <h2>Documents</h2>
      <p className="sub">Upload your DD-214, service treatment records, VA rating decisions, and
        private medical records (PDF). Scanned files are OK — pages without a text layer are
        queued for OCR.</p>
      <div
        className={`dropzone ${drag ? 'drag' : ''}`}
        onClick={() => fileInput.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); upload(e.dataTransfer.files) }}
      >
        Drop PDFs here or click to browse
        <input ref={fileInput} type="file" accept=".pdf" multiple hidden
          onChange={(e) => upload(e.target.files)} />
      </div>
      {busy && <div className="progress">{busy}</div>}
      {err && <div className="err">{err}</div>}
      {docs.length > 0 && (
        <div className="card" style={{ marginTop: 16 }}>
          <table className="tbl">
            <thead><tr><th>File</th><th>Type</th><th>Pages</th><th>Status</th><th /></tr></thead>
            <tbody>
              {docs.map((d) => (
                <tr key={d.id}>
                  <td>{d.filename}</td>
                  <td>{d.doc_type}</td>
                  <td>{d.page_count || '—'}</td>
                  <td><span className={`pill ${d.status}`}>{d.status}</span></td>
                  <td style={{ whiteSpace: 'nowrap' }}>
                    <button className="btn ghost" style={{ padding: '4px 10px', marginRight: 6 }}
                      onClick={async () => {
                        const { job_id } = await post(`/api/documents/${d.id}/reprocess`)
                        await refresh()
                        setBusy(`Reprocessing ${d.filename}…`)
                        await pollJob(job_id, (p) => setBusy(`Reprocessing ${d.filename}: ${p}`))
                        setBusy(''); refresh()
                      }}>reprocess</button>
                    <button className="btn danger" style={{ padding: '4px 10px' }}
                      onClick={() => del(`/api/documents/${d.id}`).then(refresh)}>remove</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
