import { useEffect, useState } from 'react'
import { get, post } from './api'
import Dashboard from './pages/Dashboard'
import DocumentsPage from './pages/Documents'
import DraftsPage from './pages/Drafts'
import ProfilePage from './pages/Profile'
import AnalysisPage from './pages/Analysis'
import ConditionsPage from './pages/Conditions'
import CaseFilePage from './pages/CaseFile'
import FormsPage from './pages/Forms'

const TABS = [
  ['dashboard', 'Dashboard'],
  ['documents', 'Documents'],
  ['casefile', 'Case File'],
  ['analysis', 'Analysis'],
  ['profile', 'Profile'],
  ['conditions', 'Conditions'],
  ['drafts', 'Drafts'],
  ['forms', 'Claim Forms'],
] as const

export type Tab = (typeof TABS)[number][0]

const initialTab = (): Tab => {
  const t = new URLSearchParams(window.location.search).get('tab')
  return (TABS.some(([id]) => id === t) ? t : 'dashboard') as Tab
}

export default function App() {
  const [tab, setTab] = useState<Tab>(initialTab)
  const [caseId, setCaseId] = useState<number | null>(null)
  const [llm, setLlm] = useState<{ ollama: string; missing_models: string[] } | null>(null)

  useEffect(() => {
    ;(async () => {
      const cases = await get('/api/cases')
      if (cases.length) setCaseId(cases[0].id)
      else setCaseId((await post('/api/cases', { title: 'My VA Claim' })).id)
    })().catch(console.error)
    get('/api/health').then((h) => setLlm(h.llm)).catch(() => setLlm(null))
  }, [])

  return (
    <>
      <div className="shell">
        <aside className="sidebar">
          <div className="brand">
            <h1>VetClaims <span>Local</span></h1>
            <small>self-hosted claim prep</small>
          </div>
          <nav className="nav">
            {TABS.map(([id, label]) => (
              <button key={id} className={tab === id ? 'active' : ''}
                onClick={() => setTab(id)}>{label}</button>
            ))}
          </nav>
          <div className="llm-status">
            <span className={`dot ${llm?.ollama === 'up' ? 'up' : 'down'}`} />
            Ollama {llm?.ollama ?? '…'}
            {llm && llm.missing_models.length > 0 &&
              <div>missing: {llm.missing_models.join(', ')}</div>}
          </div>
        </aside>
        <main className="main">
          {caseId === null ? <p>Loading case…</p> : {
            dashboard: <Dashboard caseId={caseId} go={setTab} />,
            documents: <DocumentsPage caseId={caseId} />,
            casefile: <CaseFilePage caseId={caseId} />,
            analysis: <AnalysisPage caseId={caseId} />,
            profile: <ProfilePage caseId={caseId} />,
            conditions: <ConditionsPage caseId={caseId} />,
            drafts: <DraftsPage caseId={caseId} />,
            forms: <FormsPage caseId={caseId} />,
          }[tab]}
        </main>
      </div>
      <footer className="disclaimer">
        VetClaims Local is not affiliated with the U.S. Department of Veterans Affairs and is not
        a VA-accredited representative, attorney, or VSO. Nothing here is legal or medical advice.
        Every generated document is a draft — review it, correct it, sign it, and file it yourself
        (e.g. on VA.gov or with a free accredited VSO). AI output can be wrong.
      </footer>
    </>
  )
}
