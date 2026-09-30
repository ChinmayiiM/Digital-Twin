import { useEffect, useState } from 'react'
import { getHealth } from '../services/api'

// status: 'checking' | 'connected' | 'failed'
export default function useHealthCheck() {
  const [status, setStatus] = useState('checking')
  const [data, setData] = useState(null)

  const check = async () => {
    setStatus('checking')
    try {
      const res = await getHealth()
      setData(res)
      setStatus(res.status === 'ok' && res.database === 'connected' ? 'connected' : 'failed')
    } catch {
      setData(null)
      setStatus('failed')
    }
  }

  useEffect(() => {
    check()
  }, [])

  return { status, data, recheck: check }
}
