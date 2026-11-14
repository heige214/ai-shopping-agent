import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

// Playwright 用 AI_PROVIDER=fake 启动 8100 后端，避免 E2E 依赖真实 DashScope。
const here = dirname(fileURLToPath(import.meta.url))
const backendDir = resolve(here, '..', '..', '..', 'backend')
const venvPython = resolve(
  backendDir,
  '.venv',
  process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python',
)
const python = existsSync(venvPython)
  ? venvPython
  : process.platform === 'win32'
    ? 'python'
    : 'python3'

const child = spawn(
  python,
  ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8100'],
  {
    cwd: backendDir,
    env: {
      ...process.env,
      AI_PROVIDER: 'fake',
      DASHSCOPE_API_KEY: '',
      PYTHONIOENCODING: 'utf-8',
      PYTHONUNBUFFERED: '1',
    },
    stdio: 'inherit',
  },
)

function shutdown(signal) {
  if (child.exitCode === null) {
    child.kill(signal)
  }
}

process.on('SIGTERM', () => shutdown('SIGTERM'))
process.on('SIGINT', () => shutdown('SIGINT'))
process.on('exit', () => shutdown('SIGTERM'))

child.on('exit', (code) => {
  process.exit(code ?? 0)
})
