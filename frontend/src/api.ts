export const getToken = () => localStorage.getItem('vc_token') ?? ''
export const setToken = (t: string) => localStorage.setItem('vc_token', t)

const hdrs = (json?: boolean): Record<string, string> => ({
  ...(json ? { 'Content-Type': 'application/json' } : {}),
  ...(getToken() ? { 'X-Auth-Token': getToken() } : {}),
})

const json = (r: Response) => {
  if (r.status === 401) {
    window.dispatchEvent(new Event('vc-auth-required'))
    return Promise.reject(new Error('authentication required'))
  }
  if (!r.ok) return r.json().then(
    (b) => Promise.reject(new Error(typeof b.detail === 'string' ? b.detail : r.statusText)),
    () => Promise.reject(new Error(r.statusText)))
  return r.json()
}

export const get = (url: string) => fetch(url, { headers: hdrs() }).then(json)
export const post = (url: string, body?: unknown) =>
  fetch(url, {
    method: 'POST',
    headers: hdrs(!!body),
    body: body ? JSON.stringify(body) : undefined,
  }).then(json)
export const put = (url: string, body: unknown) =>
  fetch(url, {
    method: 'PUT',
    headers: hdrs(true),
    body: JSON.stringify(body),
  }).then(json)
export const del = (url: string) =>
  fetch(url, { method: 'DELETE', headers: hdrs() }).then(json)

export async function downloadPdf(url: string, body?: unknown) {
  const r = await fetch(url, {
    method: 'POST',
    headers: hdrs(!!body),
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
