import { spawn } from 'node:child_process'

const baseUrl = process.env.SMARTOPSDOCS_URL || 'http://127.0.0.1:5173'
const chromeBin = process.env.CHROME_BIN || 'chromium'
const remotePort = Number(process.env.CHROME_REMOTE_PORT || 9300 + Math.floor(Math.random() * 500))
const userDataDir = `/tmp/smartopsdocs-chrome-${Date.now()}`

const chrome = spawn(
  chromeBin,
  [
    '--headless',
    '--disable-gpu',
    '--no-sandbox',
    `--remote-debugging-port=${remotePort}`,
    `--user-data-dir=${userDataDir}`,
    'about:blank'
  ],
  { stdio: ['ignore', 'ignore', 'pipe'] }
)

const errors = []
chrome.on('error', (error) => {
  console.error(`无法启动浏览器 ${chromeBin}: ${error.message}`)
  console.error('可安装 chromium，或通过 CHROME_BIN=/path/to/chrome npm run smoke 指定浏览器。')
  process.exit(1)
})
chrome.stderr.on('data', (chunk) => {
  const text = chunk.toString()
  if (/DevTools listening/.test(text)) return
  if (/DBus|UPower|snapd|libpxbackend|gio-modules|ssl_client_socket_impl|handshake failed|google_apis\/gcm|DEPRECATED_ENDPOINT/.test(text)) return
  if (/ERROR|Failed|TypeError|ReferenceError|SyntaxError/.test(text)) {
    errors.push(text.trim())
  }
})

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function getJson(url, retries = 40) {
  for (let i = 0; i < retries; i += 1) {
    try {
      const response = await fetch(url)
      if (response.ok) return response.json()
    } catch {
      await sleep(250)
    }
  }
  throw new Error(`无法连接 Chrome DevTools: ${url}`)
}

async function connect() {
  await getJson(`http://127.0.0.1:${remotePort}/json/version`)
  const targetResponse = await fetch(`http://127.0.0.1:${remotePort}/json/new?about:blank`, { method: 'PUT' })
  if (!targetResponse.ok) throw new Error('无法创建 Chrome Page target')
  const target = await targetResponse.json()
  const socket = new WebSocket(target.webSocketDebuggerUrl)
  await new Promise((resolve, reject) => {
    socket.onopen = resolve
    socket.onerror = reject
  })

  let id = 0
  const pending = new Map()
  socket.onmessage = (event) => {
    const message = JSON.parse(event.data)
    if (message.id && pending.has(message.id)) {
      const { resolve, reject } = pending.get(message.id)
      pending.delete(message.id)
      if (message.error) reject(new Error(message.error.message))
      else resolve(message.result)
    }
    if (message.method === 'Runtime.exceptionThrown') {
      errors.push(message.params.exceptionDetails.text)
    }
    if (message.method === 'Runtime.consoleAPICalled' && ['error', 'warning'].includes(message.params.type)) {
      const text = message.params.args.map((arg) => arg.value || arg.description || '').join(' ')
      if (text) errors.push(text)
    }
  }

  function send(method, params = {}) {
    id += 1
    socket.send(JSON.stringify({ id, method, params }))
    return new Promise((resolve, reject) => pending.set(id, { resolve, reject }))
  }

  await send('Runtime.enable')
  await send('Page.enable')
  return { send, close: () => socket.close() }
}

async function evaluate(cdp, expression) {
  const result = await cdp.send('Runtime.evaluate', {
    expression,
    awaitPromise: true,
    returnByValue: true
  })
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.text)
  return result.result.value
}

async function navigate(cdp, path) {
  await cdp.send('Page.navigate', { url: `${baseUrl}${path}` })
  await sleep(800)
}

async function waitFor(cdp, expression, label, retries = 30) {
  for (let i = 0; i < retries; i += 1) {
    const ok = await evaluate(cdp, expression)
    if (ok) return
    await sleep(300)
  }
  throw new Error(`等待超时: ${label}`)
}

async function main() {
  const cdp = await connect()
  try {
    await navigate(cdp, '/login')
    await waitFor(cdp, `document.body.innerText.includes('SmartOpsDocs')`, '登录页渲染')
    await evaluate(
      cdp,
      `(() => {
        const inputs = document.querySelectorAll('input')
        inputs[0].value = 'admin'
        inputs[0].dispatchEvent(new Event('input', { bubbles: true }))
        inputs[1].value = 'admin123'
        inputs[1].dispatchEvent(new Event('input', { bubbles: true }))
        document.querySelector('button').click()
        return true
      })()`
    )
    await waitFor(cdp, `location.pathname === '/servers'`, '登录跳转')

    for (const path of ['/servers', '/docker', '/k8s', '/documents', '/chat']) {
      await navigate(cdp, path)
      await waitFor(cdp, `document.querySelector('#app')?.innerText.length > 0`, `${path} 渲染`)
    }

    if (errors.length) {
      throw new Error(`浏览器错误:\n${errors.join('\n')}`)
    }
    console.log('frontend-smoke-ok')
  } finally {
    cdp.close()
    chrome.kill('SIGTERM')
  }
}

main().catch((error) => {
  chrome.kill('SIGTERM')
  console.error(error.message)
  process.exit(1)
})
