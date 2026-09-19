import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'

afterEach(() => {
  document.body.innerHTML = ''
  window.localStorage.clear()
  window.sessionStorage.clear()
})
