"use client"

import { useState, useEffect } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import { Button } from "@/components/ui/button"
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
import { ArrowLeft, Loader2, TrendingUp, TrendingDown, DollarSign, Target, PieChart, Download } from "lucide-react"
import { api } from "@/lib/api-client"
import { formatDate, formatPercent, formatCurrency, formatNumber } from "@/lib/utils"
import { MetricCard } from "@/components/metric-card"
import { EquityCurveChart } from "@/components/equity-curve-chart"

interface Metrics {
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
  winning_trades: number
  losing_trades: number
  starting_equity: number
  final_equity: number
}

interface EquityPoint {
  timestamp: string
  equity: number
}

interface Trade {
  position_id: string
  symbol: string
  direction: string
  entry_time: string
  exit_time?: string
  entry_price: number
  exit_price?: number
  quantity: number
  pnl?: number
  pnl_pct?: number
  r_multiple?: number
}

export default function ReportDetailPage() {
  const params = useParams()
  const runId = params.id as string

  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [equityCurve, setEquityCurve] = useState<EquityPoint[]>([])
  const [trades, setTrades] = useState<Trade[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadReport()
  }, [runId])

  const loadReport = async () => {
    try {
      setLoading(true)
      setError(null)

      // Load metrics
      const metricsResponse = await api.reports.metrics(runId)
      setMetrics(metricsResponse.data)

      // Load equity curve
      const equityResponse = await api.reports.equity(runId)
      setEquityCurve(equityResponse.data.data_points || [])

      // Load trades
      const tradesResponse = await api.reports.trades(runId, { page: 1, page_size: 100 })
      setTrades(tradesResponse.data.trades || [])
    } catch (err: any) {
      setError(err.message || "Failed to load report")
    } finally {
      setLoading(false)
    }
  }

  const handleExport = async () => {
    try {
      const response = await api.reports.exportTrades(runId)
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement("a")
      link.href = url
      link.setAttribute("download", `${runId}-trades.csv`)
      document.body.appendChild(link)
      link.click()
      link.remove()
    } catch (err: any) {
      setError(err.message || "Failed to export trades")
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (error || !metrics) {
    return (
      <div className="space-y-6">
        <Link href="/reports">
          <Button variant="ghost">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Reports
          </Button>
        </Link>
        <Card className="border-destructive">
          <CardContent className="pt-6">
            <p className="text-destructive">{error || "Report not found"}</p>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <Link href="/reports">
          <Button variant="ghost">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Reports
          </Button>
        </Link>
        <Button variant="outline" onClick={handleExport}>
          <Download className="mr-2 h-4 w-4" />
          Export Trades
        </Button>
      </div>

      <div>
        <h1 className="text-3xl font-bold">Performance Report</h1>
        <p className="text-muted-foreground font-mono">{runId}</p>
      </div>

      {/* Metrics Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          title="Total Return"
          value={formatCurrency(metrics.total_return)}
          subtitle={formatPercent(metrics.total_return_pct / 100)}
          icon={metrics.total_return >= 0 ? TrendingUp : TrendingDown}
          trend={metrics.total_return >= 0 ? "up" : "down"}
        />
        <MetricCard
          title="Sharpe Ratio"
          value={formatNumber(metrics.sharpe_ratio)}
          subtitle="Risk-adjusted return"
          icon={Target}
        />
        <MetricCard
          title="Max Drawdown"
          value={formatPercent(metrics.max_drawdown_pct / 100)}
          subtitle={formatCurrency(metrics.max_drawdown)}
          icon={TrendingDown}
          trend="down"
        />
        <MetricCard
          title="Win Rate"
          value={formatPercent(metrics.win_rate_pct / 100)}
          subtitle={`${metrics.winning_trades}/${metrics.total_trades} trades`}
          icon={PieChart}
          trend={metrics.win_rate > 0.5 ? "up" : "down"}
        />
      </div>

      {/* Additional Metrics */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Sortino Ratio</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{formatNumber(metrics.sortino_ratio)}</div>
            <p className="text-xs text-muted-foreground">Downside risk-adjusted</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Profit Factor</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{formatNumber(metrics.profit_factor)}</div>
            <p className="text-xs text-muted-foreground">Gross profit / Gross loss</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Total Trades</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metrics.total_trades}</div>
            <p className="text-xs text-muted-foreground">
              {metrics.winning_trades} wins • {metrics.losing_trades} losses
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Equity Curve */}
      {equityCurve.length > 0 && (
        <EquityCurveChart
          data={equityCurve}
          startingEquity={metrics.starting_equity}
          finalEquity={metrics.final_equity}
        />
      )}

      {/* Trades Table */}
      <Card>
        <CardHeader>
          <CardTitle>Trade History</CardTitle>
          <CardDescription>
            All {trades.length} trades from this run
          </CardDescription>
        </CardHeader>
        <CardContent>
          {trades.length === 0 ? (
            <p className="text-center py-8 text-muted-foreground">No trades recorded</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Symbol</TableHead>
                  <TableHead>Direction</TableHead>
                  <TableHead>Entry</TableHead>
                  <TableHead>Exit</TableHead>
                  <TableHead className="text-right">PnL</TableHead>
                  <TableHead className="text-right">PnL %</TableHead>
                  <TableHead className="text-right">R-Multiple</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {trades.slice(0, 50).map((trade) => (
                  <TableRow key={trade.position_id}>
                    <TableCell className="font-medium">{trade.symbol}</TableCell>
                    <TableCell>
                      <Badge variant={trade.direction === "long" ? "default" : "secondary"}>
                        {trade.direction}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {formatDate(trade.entry_time)}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {trade.exit_time ? formatDate(trade.exit_time) : "Open"}
                    </TableCell>
                    <TableCell className={`text-right ${trade.pnl && trade.pnl >= 0 ? "text-green-600" : "text-red-600"}`}>
                      {trade.pnl ? formatCurrency(trade.pnl) : "-"}
                    </TableCell>
                    <TableCell className={`text-right ${trade.pnl_pct && trade.pnl_pct >= 0 ? "text-green-600" : "text-red-600"}`}>
                      {trade.pnl_pct ? formatPercent(trade.pnl_pct / 100) : "-"}
                    </TableCell>
                    <TableCell className="text-right">
                      {trade.r_multiple ? `${formatNumber(trade.r_multiple)}R` : "-"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
          {trades.length > 50 && (
            <p className="text-sm text-muted-foreground text-center mt-4">
              Showing first 50 of {trades.length} trades. Export to see all.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
