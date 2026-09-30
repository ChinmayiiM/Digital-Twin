// Phase 2 has no login. The browser just remembers which user id is "the current Twin".
const KEY = 'twinmate_user_id'

export const getCurrentUserId = () => {
  try {
    return localStorage.getItem(KEY)
  } catch {
    return null
  }
}

export const setCurrentUserId = (id) => {
  try {
    localStorage.setItem(KEY, String(id))
  } catch {
    /* storage unavailable - dashboard will just ask to onboard again */
  }
}

export const clearCurrentUser = () => {
  try {
    localStorage.removeItem(KEY)
  } catch {
    /* ignore */
  }
}
