import { ref, watchEffect } from 'vue'

const THEME_KEY = 'smartopsdocs_theme'

const theme = ref(loadTheme())

function loadTheme() {
  try {
    const stored = localStorage.getItem(THEME_KEY)
    if (stored === 'dark' || stored === 'light') return stored
  } catch { /* ignore */ }
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function applyTheme(t) {
  theme.value = t
  document.documentElement.classList.toggle('dark', t === 'dark')
  try {
    localStorage.setItem(THEME_KEY, t)
  } catch { /* ignore */ }
}

function toggleTheme() {
  applyTheme(theme.value === 'dark' ? 'light' : 'dark')
}

// Apply on load
applyTheme(theme.value)

// Listen for system preference changes (only when no explicit user choice)
const mq = window.matchMedia('(prefers-color-scheme: dark)')
mq.addEventListener('change', (e) => {
  const stored = localStorage.getItem(THEME_KEY)
  if (!stored) applyTheme(e.matches ? 'dark' : 'light')
})

export default function useTheme() {
  return { theme, toggleTheme, applyTheme }
}
