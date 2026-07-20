// Capture README/docs screenshots of the running app with headless Edge.
// Usage: node scripts/screenshot.mjs [outDir]
import { execSync } from 'node:child_process'
import { mkdirSync } from 'node:fs'
import path from 'node:path'

const outDir = process.argv[2] ?? 'docs/screenshots'
mkdirSync(outDir, { recursive: true })

const edge = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const base = 'http://localhost:5173'

// tab id → filename; App reads ?tab= on load (see App.tsx)
const shots = [
  ['dashboard', 'dashboard.png'],
  ['documents', 'documents.png'],
  ['casefile', 'casefile.png'],
  ['analysis', 'analysis.png'],
  ['profile', 'profile.png'],
  ['conditions', 'conditions.png'],
  ['drafts', 'drafts.png'],
  ['forms', 'forms.png'],
]

for (const [tab, file] of shots) {
  const dest = path.join(outDir, file)
  execSync(
    `"${edge}" --headless=new --disable-gpu --force-device-scale-factor=1 ` +
    `--window-size=1440,1000 --screenshot="${path.resolve(dest)}" ` +
    `--virtual-time-budget=8000 "${base}/?tab=${tab}"`,
    { stdio: 'ignore', timeout: 60000 },
  )
  console.log('captured', dest)
}
