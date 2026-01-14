"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Loader2, Brain, AlertTriangle, RefreshCw } from "lucide-react"
import { Button } from "@/components/ui/button"
import { AgentStatusCard } from "@/components/agent-status-card"
import { api } from "@/lib/api-client"

interface AgentSummary {
  agent_name: string
  current_mode: "observe" | "active"
  model_version: string | null
  has_active_alerts: boolean
  alert_count: number
  can_graduate: boolean
  recent_decisions: number
  recent_mean_r_multiple: number | null
  recent_win_rate: number | null
}

interface AgentsOverview {
  agents: AgentSummary[]
  total_agents: number
  active_agents: number
  graduating_agents: number
  total_active_alerts: number
}

const agentDisplayNames: Record<string, string> = {
  gate: "Gate Agent",
  portfolio: "Portfolio Agent",
  meta_learner: "Meta-Learner Agent",
}

export default function RLOverviewPage() {
  const router = useRouter()
  const [overview, setOverview] = useState<AgentsOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadOverview = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await api.rl.agentsOverview()
      setOverview(response.data)
    } catch (err: any) {
      setError(err.message || "Failed to load RL overview")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadOverview()
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (error) {
    return (
      <Card className="border-destructive">
        <CardContent className="pt-6">
          <p className="text-destructive">{error}</p>
          <Button onClick={loadOverview} className="mt-4">
            <RefreshCw className="mr-2 h-4 w-4" />
            Retry
          </Button>
        </CardContent>
      </Card>
    )
  }

  if (!overview) {
    return null
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">RL Agent Monitoring</h1>
          <p className="text-muted-foreground">
            Monitor reinforcement learning agents and their training progress
          </p>
        </div>
        <Button onClick={loadOverview} variant="outline">
          <RefreshCw className="mr-2 h-4 w-4" />
          Refresh
        </Button>
      </div>

      {/* Summary Stats */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Agents
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <Brain className="h-5 w-5 text-primary" />
              <p className="text-2xl font-bold">{overview.total_agents}</p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Active Agents
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <div className="h-3 w-3 bg-green-500 rounded-full animate-pulse" />
              <p className="text-2xl font-bold">{overview.active_agents}</p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Ready to Graduate
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <Badge variant="default" className="h-fit">
                {overview.graduating_agents}
              </Badge>
              <p className="text-sm text-muted-foreground">
                agent{overview.graduating_agents !== 1 ? "s" : ""}
              </p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Active Alerts
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              {overview.total_active_alerts > 0 ? (
                <>
                  <AlertTriangle className="h-5 w-5 text-yellow-500" />
                  <p className="text-2xl font-bold text-yellow-500">
                    {overview.total_active_alerts}
                  </p>
                </>
              ) : (
                <>
                  <div className="h-5 w-5 rounded-full bg-green-500 flex items-center justify-center">
                    <span className="text-white text-xs">✓</span>
                  </div>
                  <p className="text-2xl font-bold text-green-600">0</p>
                </>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Agent Cards */}
      <div>
        <h2 className="text-xl font-semibold mb-4">Agent Status</h2>
        <div className="grid gap-4 md:grid-cols-3">
          {overview.agents.map((agent) => (
            <div
              key={agent.agent_name}
              onClick={() => router.push(`/rl/${agent.agent_name}`)}
            >
              <AgentStatusCard
                agentName={agent.agent_name}
                displayName={agentDisplayNames[agent.agent_name] || agent.agent_name}
                currentMode={agent.current_mode}
                modelVersion={agent.model_version}
                hasActiveAlerts={agent.has_active_alerts}
                alertCount={agent.alert_count}
                canGraduate={agent.can_graduate}
                recentDecisions={agent.recent_decisions}
                recentMeanRMultiple={agent.recent_mean_r_multiple}
                recentWinRate={agent.recent_win_rate}
              />
            </div>
          ))}
        </div>
      </div>

      {/* Info Card */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">About RL Agents</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          <p>
            <strong>Gate Agent:</strong> Learns to filter candidates based on entry quality,
            reducing transaction costs by rejecting low-probability setups.
          </p>
          <p>
            <strong>Portfolio Agent:</strong> Learns optimal position sizing based on market
            conditions, volatility, and portfolio composition.
          </p>
          <p>
            <strong>Meta-Learner:</strong> Learns when to override LLM decisions, acting as a
            safety layer and performance enhancer.
          </p>
          <p className="pt-2 border-t">
            Agents start in <Badge variant="secondary">observe</Badge> mode to collect training
            data. Once graduation requirements are met, they transition to{" "}
            <Badge variant="success">active</Badge> mode to make real decisions.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
