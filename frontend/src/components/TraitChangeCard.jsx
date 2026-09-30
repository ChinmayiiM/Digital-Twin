/** One changed Twin trait: BEFORE -> AFTER, with the reason. Every value comes from the backend diff. */
export default function TraitChangeCard({ change }) {
  const rows = [
    ['Value', change.before_short, change.after_short],
    ['Evidence', `${change.evidence_before} obs.`, `${change.evidence_after} obs.`],
    ['Confidence', `${change.confidence_label_before} (${Math.round(change.confidence_before * 100)}%)`,
      `${change.confidence_label_after} (${Math.round(change.confidence_after * 100)}%)`],
  ]
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <p className="font-semibold text-slate-900">{change.label}</p>
      <table className="mt-2 w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-slate-500">
            <th className="py-1 font-medium" /><th className="py-1 font-medium">Before</th><th className="py-1 font-medium">After</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([label, before, after]) => (
            <tr key={label} className="border-t border-slate-100">
              <td className="py-1.5 pr-2 text-slate-500">{label}</td>
              <td className="py-1.5 pr-2 text-slate-600">{before}</td>
              <td className={`py-1.5 font-semibold ${before !== after ? 'text-indigo-700' : 'text-slate-900'}`}>{after}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-3 text-sm text-slate-700"><strong>Why did this change?</strong> {change.reason}</p>
      {change.formula && (
        <p className="mt-1 text-xs text-slate-500">Update: {change.formula}</p>
      )}
    </div>
  )
}
