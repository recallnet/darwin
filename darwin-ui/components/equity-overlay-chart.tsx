"use client"

import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { formatCurrency, formatDate } from "@/lib/utils"

interface EquityOverlayPoint {
  timestamp: string
  equities: Record<string, number>
}

interface EquityOverlayChartProps {
  runIds: string[]
  startingEquity: Record<string, number>
  finalEquity: Record<string, number>
  dataPoints: EquityOverlayPoint[]
}

const COLORS = [
  "hsl(var(--primary))",
  "#10b981", // green
  "#f59e0b", // amber
  "#ef4444", // red
  "#8b5cf6", // purple
  "#06b6d4", // cyan
  "#ec4899", // pink
  "#84cc16", // lime
]

export function EquityOverlayChart({
  runIds,
  startingEquity,
  finalEquity,
  dataPoints,
}: EquityOverlayChartProps) {
  // Transform data for recharts
  const chartData = dataPoints.map((point) => ({
    timestamp: new Date(point.timestamp).getTime(),
    ...point.equities,
  }))

  return (
    <Card>
      <CardHeader>
        <CardTitle>Equity Curve Overlay</CardTitle>
        <CardDescription>
          Compare portfolio performance over time across {runIds.length} runs
        </CardDescription>
      </CardHeader>
      <CardContent>
        {/* Legend with returns */}
        <div className="mb-4 grid gap-2 md:grid-cols-2 lg:grid-cols-3">
          {runIds.map((runId, index) => {
            const start = startingEquity[runId] || 0
            const end = finalEquity[runId] || 0
            const returnPct = start > 0 ? ((end - start) / start) * 100 : 0

            return (
              <div key={runId} className="flex items-center gap-2 text-sm">
                <div
                  className="h-3 w-3 rounded-full"
                  style={{ backgroundColor: COLORS[index % COLORS.length] }}
                />
                <span className="font-mono text-xs">{runId}</span>
                <span className={returnPct >= 0 ? "text-green-600" : "text-red-600"}>
                  {returnPct >= 0 ? "+" : ""}{returnPct.toFixed(2)}%
                </span>
              </div>
            )
          })}
        </div>

        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
            <XAxis
              dataKey="timestamp"
              type="number"
              domain={["dataMin", "dataMax"]}
              tickFormatter={(timestamp) => {
                const date = new Date(timestamp)
                return date.toLocaleDateString("en-US", { month: "short", day: "numeric" })
              }}
              className="text-xs"
            />
            <YAxis
              tickFormatter={(value) => formatCurrency(value, 0)}
              className="text-xs"
            />
            <Tooltip
              labelFormatter={(timestamp) => formatDate(new Date(timestamp as number))}
              formatter={(value: number, name: string) => [formatCurrency(value), name]}
              contentStyle={{
                backgroundColor: "hsl(var(--card))",
                border: "1px solid hsl(var(--border))",
                borderRadius: "var(--radius)",
              }}
            />
            <Legend />
            {runIds.map((runId, index) => (
              <Line
                key={runId}
                type="monotone"
                dataKey={runId}
                name={runId}
                stroke={COLORS[index % COLORS.length]}
                strokeWidth={2}
                dot={false}
                animationDuration={300}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}
