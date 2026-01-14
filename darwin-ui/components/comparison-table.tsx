"use client"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Crown } from "lucide-react"
import { formatPercent, formatNumber, formatCurrency } from "@/lib/utils"

interface RunMetrics {
  run_id: string
  description: string
  symbols: string[]
  playbooks: string[]
  total_return: number
  total_return_pct: number
  sharpe_ratio: number
  sortino_ratio: number
  max_drawdown: number
  max_drawdown_pct: number
  win_rate: number
  win_rate_pct: number
  profit_factor: number
  total_trades: number
  final_equity: number
}

interface ComparisonTableProps {
  runs: RunMetrics[]
  bestByMetric: Record<string, string>
}

export function ComparisonTable({ runs, bestByMetric }: ComparisonTableProps) {
  const isBest = (runId: string, metric: string) => {
    return bestByMetric[metric] === runId
  }

  const metrics = [
    { key: "total_return_pct", label: "Total Return", format: (v: number) => formatPercent(v / 100) },
    { key: "sharpe_ratio", label: "Sharpe Ratio", format: formatNumber },
    { key: "sortino_ratio", label: "Sortino Ratio", format: formatNumber },
    { key: "max_drawdown_pct", label: "Max Drawdown", format: (v: number) => formatPercent(v / 100) },
    { key: "win_rate_pct", label: "Win Rate", format: (v: number) => formatPercent(v / 100) },
    { key: "profit_factor", label: "Profit Factor", format: formatNumber },
    { key: "total_trades", label: "Total Trades", format: (v: number) => v.toString() },
    { key: "final_equity", label: "Final Equity", format: formatCurrency },
  ]

  return (
    <Card>
      <CardHeader>
        <CardTitle>Side-by-Side Comparison</CardTitle>
        <CardDescription>
          Compare key metrics across selected runs
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[200px] sticky left-0 bg-card">Metric</TableHead>
                {runs.map((run) => (
                  <TableHead key={run.run_id} className="min-w-[150px]">
                    <div className="space-y-1">
                      <div className="font-mono text-xs">{run.run_id}</div>
                      <div className="text-xs text-muted-foreground font-normal">
                        {run.description}
                      </div>
                    </div>
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {/* Symbols & Playbooks */}
              <TableRow>
                <TableCell className="font-medium sticky left-0 bg-card">Symbols</TableCell>
                {runs.map((run) => (
                  <TableCell key={run.run_id}>
                    <div className="flex flex-wrap gap-1">
                      {run.symbols.map((symbol) => (
                        <Badge key={symbol} variant="outline" className="text-xs">
                          {symbol}
                        </Badge>
                      ))}
                    </div>
                  </TableCell>
                ))}
              </TableRow>
              <TableRow>
                <TableCell className="font-medium sticky left-0 bg-card">Playbooks</TableCell>
                {runs.map((run) => (
                  <TableCell key={run.run_id}>
                    <div className="flex flex-wrap gap-1">
                      {run.playbooks.map((playbook) => (
                        <Badge key={playbook} variant="secondary" className="text-xs">
                          {playbook}
                        </Badge>
                      ))}
                    </div>
                  </TableCell>
                ))}
              </TableRow>

              {/* Metrics */}
              {metrics.map((metric) => (
                <TableRow key={metric.key}>
                  <TableCell className="font-medium sticky left-0 bg-card">
                    {metric.label}
                  </TableCell>
                  {runs.map((run) => {
                    const value = run[metric.key as keyof RunMetrics] as number
                    const best = isBest(run.run_id, metric.key)

                    return (
                      <TableCell key={run.run_id}>
                        <div className="flex items-center gap-2">
                          {best && (
                            <Crown className="h-4 w-4 text-yellow-500" />
                          )}
                          <span className={best ? "font-semibold" : ""}>
                            {metric.format(value)}
                          </span>
                        </div>
                      </TableCell>
                    )
                  })}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  )
}
