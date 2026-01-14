"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Loader2, GitCompare, Download, TrendingUp } from "lucide-react"
import { RunSelector } from "@/components/run-selector"
import { ComparisonTable } from "@/components/comparison-table"
import { EquityOverlayChart } from "@/components/equity-overlay-chart"
import { api } from "@/lib/api-client"

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

interface ComparisonData {
  runs: RunMetrics[]
  best_by_metric: Record<string, string>
}

interface OverlayData {
  run_ids: string[]
  starting_equity: Record<string, number>
  final_equity: Record<string, number>
  data_points: Array<{
    timestamp: string
    equities: Record<string, number>
  }>
}

interface RankingEntry {
  rank: number
  run_id: string
  description: string
  value: number
  symbols: string[]
  playbooks: string[]
}

export default function ComparePage() {
  const [selectedRuns, setSelectedRuns] = useState<string[]>([])
  const [comparison, setComparison] = useState<ComparisonData | null>(null)
  const [overlay, setOverlay] = useState<OverlayData | null>(null)
  const [rankings, setRankings] = useState<RankingEntry[] | null>(null)
  const [selectedMetric, setSelectedMetric] = useState("sharpe_ratio")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleCompare = async () => {
    if (selectedRuns.length < 2) {
      setError("Please select at least 2 runs to compare")
      return
    }

    try {
      setLoading(true)
      setError(null)

      // Load comparison data
      const comparisonResponse = await api.meta.compare(selectedRuns)
      setComparison(comparisonResponse.data)

      // Load overlay data
      const overlayResponse = await api.meta.overlay(selectedRuns)
      setOverlay(overlayResponse.data)

      // Load rankings
      const rankingsResponse = await api.meta.rankings(selectedMetric, selectedRuns)
      setRankings(rankingsResponse.data.rankings)
    } catch (err: any) {
      setError(err.message || "Failed to compare runs")
    } finally {
      setLoading(false)
    }
  }

  const handleExport = async () => {
    if (selectedRuns.length < 2) return

    try {
      const response = await api.meta.exportComparison(selectedRuns)
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement("a")
      link.href = url
      link.setAttribute("download", "comparison.csv")
      document.body.appendChild(link)
      link.click()
      link.remove()
    } catch (err: any) {
      setError(err.message || "Failed to export comparison")
    }
  }

  const metricOptions = [
    { value: "sharpe_ratio", label: "Sharpe Ratio" },
    { value: "total_return", label: "Total Return" },
    { value: "sortino_ratio", label: "Sortino Ratio" },
    { value: "win_rate", label: "Win Rate" },
    { value: "profit_factor", label: "Profit Factor" },
    { value: "max_drawdown", label: "Max Drawdown" },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Compare Strategies</h1>
        <p className="text-muted-foreground">
          Compare multiple backtest runs side-by-side to identify the best performing strategies
        </p>
      </div>

      {error && (
        <Card className="border-destructive">
          <CardContent className="pt-6">
            <p className="text-destructive">{error}</p>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-1">
          <RunSelector
            selectedRuns={selectedRuns}
            onSelectionChange={setSelectedRuns}
          />

          <Card className="mt-4">
            <CardHeader>
              <CardTitle className="text-sm">Actions</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <Button
                className="w-full"
                onClick={handleCompare}
                disabled={selectedRuns.length < 2 || loading}
              >
                {loading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Comparing...
                  </>
                ) : (
                  <>
                    <GitCompare className="mr-2 h-4 w-4" />
                    Compare Runs
                  </>
                )}
              </Button>

              {comparison && (
                <Button
                  variant="outline"
                  className="w-full"
                  onClick={handleExport}
                >
                  <Download className="mr-2 h-4 w-4" />
                  Export CSV
                </Button>
              )}

              {selectedRuns.length > 0 && (
                <div className="pt-2 text-xs text-muted-foreground">
                  {selectedRuns.length} run{selectedRuns.length !== 1 && "s"} selected
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="lg:col-span-2 space-y-6">
          {!comparison && !loading && (
            <Card>
              <CardContent className="pt-6">
                <div className="text-center py-12">
                  <GitCompare className="mx-auto h-12 w-12 text-muted-foreground" />
                  <h3 className="mt-4 text-lg font-semibold">No Comparison Yet</h3>
                  <p className="text-sm text-muted-foreground mt-2">
                    Select at least 2 runs and click "Compare Runs" to see the results
                  </p>
                </div>
              </CardContent>
            </Card>
          )}

          {loading && (
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                </div>
              </CardContent>
            </Card>
          )}

          {comparison && overlay && (
            <>
              {/* Rankings */}
              {rankings && rankings.length > 0 && (
                <Card>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <div>
                        <CardTitle>Rankings</CardTitle>
                        <CardDescription>
                          Runs ranked by selected metric
                        </CardDescription>
                      </div>
                      <select
                        value={selectedMetric}
                        onChange={(e) => setSelectedMetric(e.target.value)}
                        className="rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      >
                        {metricOptions.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      {rankings.slice(0, 5).map((entry) => (
                        <div
                          key={entry.run_id}
                          className="flex items-center gap-4 rounded-lg border p-3"
                        >
                          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-primary-foreground font-bold">
                            {entry.rank}
                          </div>
                          <div className="flex-1">
                            <div className="font-mono text-sm font-medium">
                              {entry.run_id}
                            </div>
                            <div className="text-xs text-muted-foreground">
                              {entry.description}
                            </div>
                          </div>
                          <div className="text-right">
                            <div className="font-semibold">
                              {typeof entry.value === "number"
                                ? entry.value.toFixed(2)
                                : entry.value}
                            </div>
                            {entry.rank === 1 && (
                              <Badge variant="default" className="mt-1">
                                <TrendingUp className="mr-1 h-3 w-3" />
                                Best
                              </Badge>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Comparison Table */}
              <ComparisonTable
                runs={comparison.runs}
                bestByMetric={comparison.best_by_metric}
              />

              {/* Overlay Chart */}
              <EquityOverlayChart
                runIds={overlay.run_ids}
                startingEquity={overlay.starting_equity}
                finalEquity={overlay.final_equity}
                dataPoints={overlay.data_points}
              />
            </>
          )}
        </div>
      </div>
    </div>
  )
}
