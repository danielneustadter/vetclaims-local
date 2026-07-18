const json = (r: Response) => {
  if (!r.ok) return r.json().then(
    (b) => Promise.reject(new Error(b.detail ?? r.statusText)),
    () => Promise.reject(new Error(r.statusText)))
  return r.json()
}

export const get = (url: string) => fetch(url).then(json)
export const post = (url: string, body?: unknown) =>
  fetch(url, {
    method: 'POST',
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  }).then(json)
export const put = (url: string, body: unknown) =>
  fetch(url, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }).then(json)
export const del = (url: string) => fetch(url, { method: 'DELETE' }).then(json)

export async function downloadPdf(url: string, body?: unknown) {
  const r = await fetch(url, {
    method: 'POST',
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!r.ok) {
    const detail = await r.json().then((b) => b.detail).catch(() => r.statusText)
    throw new Error(detail)
  }
  const blob = await r.blob()
  const dispo = r.headers.get('Content-Disposition') ?? ''
  const name = /filename="?([^";]+)"?/.exec(dispo)?.[1] ?? 'form.pdf'
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = name
  a.click()
  URL.revokeObjectURL(a.href)
  return name
}

export async function pollJob(jobId: number, onProgress?: (p: string) => void) {
  for (;;) {
    const job = await get(`/api/jobs/${jobId}`)
    if (job.status === 'done') return job
    if (job.status === 'error') throw new Error(job.error ?? 'job failed')
    onProgress?.(job.progress || job.status)
    await new Promise((res) => setTimeout(res, 1500))
  }
}
