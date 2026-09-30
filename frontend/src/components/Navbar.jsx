import { Link, NavLink } from 'react-router-dom'

const linkClass = ({ isActive }) =>
  `rounded-lg px-3 py-1.5 text-sm font-medium transition ${
    isActive ? 'bg-indigo-50 text-indigo-700' : 'text-slate-500 hover:text-slate-900'
  }`

export default function Navbar({ userName, onStartOver }) {
  return (
    <header className="border-b border-slate-200 bg-white/80 backdrop-blur">
      <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-2 px-6 py-3">
        <div className="flex items-center gap-6">
          <Link to="/" className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-sm font-bold text-white">T</span>
            <span className="text-lg font-bold tracking-tight text-slate-900">TwinMate AI</span>
          </Link>
          {userName && (
            <nav className="flex items-center gap-1">
              <NavLink to="/dashboard" className={linkClass}>Dashboard</NavLink>
              <NavLink to="/twin" className={linkClass}>Digital Twin</NavLink>
              <NavLink to="/simulator" className={linkClass}>What-If Simulator</NavLink>
              <NavLink to="/privacy" className={linkClass}>Privacy &amp; Data</NavLink>
            </nav>
          )}
        </div>
        <div className="flex items-center gap-4">
          {userName && <span className="text-sm text-slate-600">Welcome, <strong>{userName}</strong></span>}
          {onStartOver && (
            <button onClick={onStartOver} className="text-sm font-medium text-slate-400 hover:text-indigo-600">
              Start over
            </button>
          )}
        </div>
      </div>
    </header>
  )
}
