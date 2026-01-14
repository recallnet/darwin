"use client"

import { useState, useEffect } from "react"
import { useParams, useRouter } from "next/navigation"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Loader2,
  ArrowLeft,
  Activity,
  TrendingUp,
  AlertCircle,
  Clock,
  CheckCircle,
  RefreshCw,
} from "lucide-react"
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts"
import { GraduationProgress } from "@/components/graduation-progress"
import { TensorboardViewer } from "@/components/tensorboard-viewer"
import { MultiRunTraining } from "@/components/multi-run-training"
import { api } from "@/lib/api-client"
import { formatDate } from "@/lib/utils"

const agentDisplayNames: Record<string, string> = {
  gate: "Gate Agent",
  portfolio: "Portfolio Agent",
  meta_learner: "Meta-Learner Agent",
}

interface AgentDetail {
  agent_name: string
  current_mode: "observe" | "active"
  model_version: string | null
  total_decisions: number
  active_alerts: Alert[]
  last_decision_at: string | null
}

interface PerformanceMetrics {
  window_days: number
  decision_count: number
  mean_r_multiple: number | null
  win_rate: number | null
  sharpe_ratio: number | null
  total_reward: number | null
}

interface GraduationStatus {
  can_graduate: boolean
  requirements: Array<{
    name: string
    met: boolean
    current: number | null
    required: number | null
    unit: string
  }>
  stability_score: number | null
  performance_vs_baseline: number | null
}

interface Alert {
  alert_type: string
  severity: "low" | "medium" | "high" | "critical"
  message: string
  triggered_at: string
  metadata: Record<string, any>
}

interface Decision {
  decision_id: string
  timestamp: string
  decision_type: string
  action: string
  confidence: number | null
  reward: number | null
}

interface MetricHistory {
  timestamp: string
  mean_r_multiple: number
  win_rate: number
  decision_count: number
}

export default function AgentDetailPage() {
  const params = useParams()
  const router = useRouter()
  const agentName = params.agent as string

  const [detail, setDetail] = useState<AgentDetail | null>(null)
  const [metrics, setMetrics] = useState<PerformanceMetrics | null>(null)
  const [metricsHistory, setMetricsHistory] = useState<MetricHistory[]>([])
  const [graduation, setGraduation] = useState<GraduationStatus | null>(null)
  const [decisions, setDecisions] = useState<Decision[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadAgentData = async () => {
    try {
      setLoading(true)
      setError(null)

      const [detailRes, metricsRes, metricsHistoryRes, graduationRes, decisionsRes] =
        await Promise.all([
          api.rl.agentDetail(agentName),
          api.rl.metrics(agentName, 30),
          api.rl.metricsHistory(agentName, 30),
          api.rl.graduation(agentName),
          api.rl.decisions(agentName, { limit: 20 }),
        ])

      setDetail(detailRes.data)
      setMetrics(metricsRes.data)
      setMetricsHistory(metricsHistoryRes.data.history || [])
      setGraduation(graduationRes.data)
      setDecisions(decisionsRes.data.decisions || [])
    } catch (err: any) {
      setError(err.message || "Failed to load agent data")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadAgentData()
  }, [agentName])

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (error || !detail) {
    return (
      <Card className="border-destructive">
        <CardContent className="pt-6">
          <p className="text-destructive">{error || "Agent not found"}</p>
          <Button onClick={() => router.back()} className="mt-4">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Go Back
          </Button>
        </CardContent>
      </Card>
    )
  }

  const displayName = agentDisplayNames[agentName] || agentName
  const modeColor = detail.current_mode === "active" ? "success" : "secondary"

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button onClick={() => router.back()} variant="outline" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-3xl font-bold">{displayName}</h1>
              <Badge variant={modeColor}>
                {detail.current_mode === "active" && <Activity className="h-4 w-4 mr-1" />}
                {detail.current_mode}
              </Badge>
            </div>
            <p className="text-muted-foreground">
              Model: {detail.model_version || "No model trained"}
            </p>
          </div>
        </div>
        <Button onClick={loadAgentData} variant="outline">
          <RefreshCw className="mr-2 h-4 w-4" />
          Refresh
        </Button>
      </div>

      {/* Stats Overview */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Decisions
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{detail.total_decisions.toLocaleString()}</p>
          </CardContent>
        </Card>

        {metrics && (
          <>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  30-Day Decisions
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold">{metrics.decision_count.toLocaleString()}</p>
              </CardContent>
            </Card>

            {metrics.mean_r_multiple !== null && (
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    Mean R-Multiple (30d)
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center gap-2">
                    {metrics.mean_r_multiple >= 0 ? (
                      <TrendingUp className="h-5 w-5 text-green-600" />
                    ) : (
                      <TrendingUp className="h-5 w-5 text-red-600 rotate-180" />
                    )}
                    <p
                      className={`text-2xl font-bold ${
                        metrics.mean_r_multiple >= 0 ? "text-green-600" : "text-red-600"
                      }`}
                    >
                      {metrics.mean_r_multiple.toFixed(2)}
                    </p>
                  </div>
                </CardContent>
              </Card>
            )}

            {metrics.win_rate !== null && (
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    Win Rate (30d)
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-2xl font-bold">{(metrics.win_rate * 100).toFixed(1)}%</p>
                </CardContent>
              </Card>
            )}
          </>
        )}
      </div>

      {/* Alerts */}
      {detail.active_alerts.length > 0 && (
        <Card className="border-yellow-200 bg-yellow-50">
          <CardHeader>
            <div className="flex items-center gap-2">
              <AlertCircle className="h-5 w-5 text-yellow-600" />
              <CardTitle className="text-base">Active Alerts</CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {detail.active_alerts.map((alert, idx) => (
                <div
                  key={idx}
                  className="flex items-start gap-3 p-3 bg-white rounded-lg border"
                >
                  <Badge
                    variant={
                      alert.severity === "critical"
                        ? "destructive"
                        : alert.severity === "high"
                        ? "destructive"
                        : "warning"
                    }
                  >
                    {alert.severity}
                  </Badge>
                  <div className="flex-1">
                    <p className="text-sm font-medium">{alert.alert_type}</p>
                    <p className="text-xs text-muted-foreground">{alert.message}</p>
                    <p className="text-xs text-muted-foreground mt-1">
                      <Clock className="h-3 w-3 inline mr-1" />
                      {formatDate(new Date(alert.triggered_at))}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Tabs */}
      <Tabs defaultValue="performance" className="space-y-4">
        <TabsList>
          <TabsTrigger value="performance">Performance</TabsTrigger>
          <TabsTrigger value="graduation">Graduation</TabsTrigger>
          <TabsTrigger value="tensorboard">Tensorboard</TabsTrigger>
          <TabsTrigger value="training">Multi-Run Training</TabsTrigger>
          <TabsTrigger value="decisions">Recent Decisions</TabsTrigger>
        </TabsList>

        {/* Performance Tab */}
        <TabsContent value="performance" className="space-y-4">
          {metricsHistory.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Performance Trends (30 Days)</CardTitle>
                <CardDescription>
                  Mean R-Multiple and Win Rate over time
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={metricsHistory}>
                    <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                    <XAxis
                      dataKey="timestamp"
                      tickFormatter={(ts) =>
                        new Date(ts).toLocaleDateString("en-US", {
                          month: "short",
                          day: "numeric",
                        })
                      }
                      className="text-xs"
                    />
                    <YAxis className="text-xs" />
                    <Tooltip
                      labelFormatter={(ts) => formatDate(new Date(ts as string))}
                      formatter={(value: number, name: string) => [
                        name === "win_rate" ? `${(value * 100).toFixed(1)}%` : value.toFixed(2),
                        name === "mean_r_multiple" ? "R-Multiple" : "Win Rate",
                      ]}
                      contentStyle={{
                        backgroundColor: "hsl(var(--card))",
                        border: "1px solid hsl(var(--border))",
                        borderRadius: "var(--radius)",
                      }}
                    />
                    <Legend />
                    <Line
                      type="monotone"
                      dataKey="mean_r_multiple"
                      name="R-Multiple"
                      stroke="hsl(var(--primary))"
                      strokeWidth={2}
                      dot={false}
                    />
                    <Line
                      type="monotone"
                      dataKey="win_rate"
                      name="Win Rate"
                      stroke="#10b981"
                      strokeWidth={2}
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Graduation Tab */}
        <TabsContent value="graduation">
          {graduation && (
            <GraduationProgress
              agentName={displayName}
              canGraduate={graduation.can_graduate}
              requirements={graduation.requirements}
              stabilityScore={graduation.stability_score}
              performanceVsBaseline={graduation.performance_vs_baseline}
            />
          )}
        </TabsContent>

        {/* Tensorboard Tab */}
        <TabsContent value="tensorboard">
          <TensorboardViewer agentName={agentName} />
        </TabsContent>

        {/* Multi-Run Training Tab */}
        <TabsContent value="training">
          <MultiRunTraining agentName={agentName} />
        </TabsContent>

        {/* Decisions Tab */}
        <TabsContent value="decisions">
          <Card>
            <CardHeader>
              <CardTitle>Recent Decisions</CardTitle>
              <CardDescription>Last 20 decisions made by this agent</CardDescription>
            </CardHeader>
            <CardContent>
              {decisions.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-8">
                  No decisions recorded yet
                </p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Timestamp</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Action</TableHead>
                      <TableHead>Confidence</TableHead>
                      <TableHead>Reward</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {decisions.map((decision) => (
                      <TableRow key={decision.decision_id}>
                        <TableCell className="text-xs">
                          {formatDate(new Date(decision.timestamp))}
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline" className="text-xs">
                            {decision.decision_type}
                          </Badge>
                        </TableCell>
                        <TableCell className="font-medium">{decision.action}</TableCell>
                        <TableCell>
                          {decision.confidence !== null
                            ? `${(decision.confidence * 100).toFixed(0)}%`
                            : "-"}
                        </TableCell>
                        <TableCell>
                          {decision.reward !== null ? (
                            <span
                              className={
                                decision.reward >= 0 ? "text-green-600" : "text-red-600"
                              }
                            >
                              {decision.reward >= 0 ? "+" : ""}
                              {decision.reward.toFixed(2)}
                            </span>
                          ) : (
                            "-"
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
