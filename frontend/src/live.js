import { useEffect, useRef } from 'react'

/**
 * Keeps a page's data fresh without websockets: re-runs `fn` every
 * `intervalMs` while the tab is visible, and immediately when the app
 * returns to the foreground (PWA resume / tab switch / window focus).
 * `fn` must be a silent refetch — swallow transient network errors, or a
 * blip while the phone sleeps paints an error over an otherwise-fine page.
 */
export function useLiveRefresh(fn, intervalMs = 15000) {
  const fnRef = useRef(fn)
  fnRef.current = fn

  useEffect(() => {
    const run = () => {
      if (document.visibilityState === 'visible') fnRef.current()
    }
    const timer = setInterval(run, intervalMs)
    document.addEventListener('visibilitychange', run)
    window.addEventListener('focus', run)
    return () => {
      clearInterval(timer)
      document.removeEventListener('visibilitychange', run)
      window.removeEventListener('focus', run)
    }
  }, [intervalMs])
}
