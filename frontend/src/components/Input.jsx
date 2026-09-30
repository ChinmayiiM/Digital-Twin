const base =
  'w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100'

function Field({ label, hint, children }) {
  return (
    <label className="block">
      {label && <span className="mb-1 block text-sm font-medium text-slate-700">{label}</span>}
      {children}
      {hint && <span className="mt-1 block text-xs text-slate-400">{hint}</span>}
    </label>
  )
}

export default function Input({ label, hint, ...props }) {
  return (
    <Field label={label} hint={hint}>
      <input className={base} {...props} />
    </Field>
  )
}

export function Textarea({ label, hint, ...props }) {
  return (
    <Field label={label} hint={hint}>
      <textarea rows={2} className={base} {...props} />
    </Field>
  )
}

export function Select({ label, hint, options, ...props }) {
  return (
    <Field label={label} hint={hint}>
      <select className={base} {...props}>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </Field>
  )
}
