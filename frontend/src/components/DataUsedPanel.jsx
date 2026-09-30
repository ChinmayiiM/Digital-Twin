/** "Data used for this recommendation": every category, whether it was permitted, and what was used.
 *  The list comes from the backend (the same data the simulator actually read). */
export default function DataUsedPanel({ categories }) {
  if (!categories || categories.length === 0) {
    return <p className="text-sm text-slate-400">No data-use record is available for this recommendation.</p>
  }
  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
      {categories.map((c) => (
        <div key={c.key} className="rounded-lg border border-slate-100 p-3">
          <div className="flex items-center justify-between gap-2">
            <p className="font-medium text-slate-800">{c.label}</p>
            <span className={`shrink-0 rounded-full border px-2 py-0.5 text-xs font-medium ${
              c.permitted ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-slate-200 bg-slate-100 text-slate-500'
            }`}>
              {c.permitted ? 'Permitted' : 'Permission off'}
            </span>
          </div>
          {c.items.length > 0 && (
            <ul className="mt-2 space-y-1 text-sm">
              {c.items.map((i) => (
                <li key={i.name} className="text-slate-700">
                  <span className="text-emerald-600">✓</span> {i.name}
                  {i.value && <strong className="text-slate-900">: {i.value}</strong>}
                  {i.detail && <span className="text-xs text-slate-400"> ({i.detail})</span>}
                </li>
              ))}
            </ul>
          )}
          {c.note && <p className="mt-2 text-xs text-slate-500">{c.note}</p>}
          {c.items.length === 0 && !c.note && <p className="mt-2 text-xs text-slate-400">Nothing from this category was used.</p>}
        </div>
      ))}
    </div>
  )
}
