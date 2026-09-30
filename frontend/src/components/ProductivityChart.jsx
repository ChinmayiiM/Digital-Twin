import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

/** Bars for morning / afternoon / evening. A period without enough evidence has value null -> no bar. */
export default function ProductivityChart({ traits }) {
  const data = traits.map((t) => ({
    name: t.display_name.replace(' productivity', ''),
    percent: t.sufficient_evidence && t.trait_value != null ? Math.round(t.trait_value * 100) : null,
  }))

  return (
    <div style={{ width: '100%', height: 200 }}>
      <ResponsiveContainer>
        <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="name" tickLine={false} />
          <YAxis domain={[0, 100]} unit="%" tickLine={false} />
          <Tooltip formatter={(v) => [`${v}%`, 'Productivity']} />
          <Bar dataKey="percent" fill="#6366f1" radius={[6, 6, 0, 0]} maxBarSize={56} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
