"use client"

import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { formatCurrency, formatDate } from "@/lib/utils"

interface EquityCurvePoint {
  timestamp: string
  equity: number
}

interface EquityCurveChartProps {
  data: EquityCurvePoint[]
  startingEquity: number
  finalEquity: number
}

export function EquityCurveChart({ data, startingEquity, finalEquity }: EquityCurveChartProps) {
  const totalReturn = finalEquity - startingEquity
  const totalReturnPct = ((totalReturn / startingEquity) * 100).toFixed(2)

  const chartData = data.map((point) => ({
    timestamp: new Date(point.timestamp).getTime(),
    equity: point.equity,
  }))

  return (
    <Card>
      <CardHeader>
        <CardTitle>Equity Curve</CardTitle>
        <CardDescription>
          Portfolio value over time
          {" • "}
          Total Return: <span className={totalReturn >= 0 ? "text-green-600" : "text-red-600"}>
            {formatCurrency(totalReturn)} ({totalReturnPct}%)
          </span>
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={350}>
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
              formatter={(value: number) => [formatCurrency(value), "Equity"]}
              contentStyle={{
                backgroundColor: "hsl(var(--card))",
                border: "1px solid hsl(var(--border))",
                borderRadius: "var(--radius)",
              }}
            />
            <Line
              type="monotone"
              dataKey="equity"
              stroke="hsl(var(--primary))"
              strokeWidth={2}
              dot={false}
              animationDuration={300}
            />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}
