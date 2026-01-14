"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Activity, AlertCircle, CheckCircle, TrendingUp, TrendingDown } from "lucide-react"

interface AgentStatusCardProps {
  agentName: string
  displayName: string
  currentMode: "observe" | "active"
  modelVersion: string | null
  hasActiveAlerts: boolean
  alertCount: number
  canGraduate: boolean
  recentDecisions: number
  recentMeanRMultiple: number | null
  recentWinRate: number | null
}

export function AgentStatusCard({
  agentName,
  displayName,
  currentMode,
  modelVersion,
  hasActiveAlerts,
  alertCount,
  canGraduate,
  recentDecisions,
  recentMeanRMultiple,
  recentWinRate,
}: AgentStatusCardProps) {
  const modeColor = currentMode === "active" ? "success" : "secondary"
  const modeIcon = currentMode === "active" ? <Activity className="h-4 w-4" /> : null

  return (
    <Card className="hover:shadow-md transition-shadow cursor-pointer">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg font-semibold">{displayName}</CardTitle>
          <Badge variant={modeColor}>
            {modeIcon}
            <span className="ml-1">{currentMode}</span>
          </Badge>
        </div>
        <div className="flex items-center gap-2 mt-2">
          {canGraduate && (
            <Badge variant="default" className="text-xs">
              <CheckCircle className="h-3 w-3 mr-1" />
              Ready to Graduate
            </Badge>
          )}
          {hasActiveAlerts && (
            <Badge variant="destructive" className="text-xs">
              <AlertCircle className="h-3 w-3 mr-1" />
              {alertCount} Alert{alertCount !== 1 ? "s" : ""}
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {/* Model Version */}
          <div>
            <p className="text-xs text-muted-foreground">Model Version</p>
            <p className="text-sm font-mono">
              {modelVersion || "No model trained"}
            </p>
          </div>

          {/* Recent Activity */}
          <div>
            <p className="text-xs text-muted-foreground">Recent Decisions (30d)</p>
            <p className="text-lg font-semibold">{recentDecisions.toLocaleString()}</p>
          </div>

          {/* Performance Metrics */}
          {recentMeanRMultiple !== null && (
            <div className="grid grid-cols-2 gap-2">
              <div>
                <p className="text-xs text-muted-foreground">Mean R-Multiple</p>
                <div className="flex items-center gap-1">
                  {recentMeanRMultiple >= 0 ? (
                    <TrendingUp className="h-4 w-4 text-green-600" />
                  ) : (
                    <TrendingDown className="h-4 w-4 text-red-600" />
                  )}
                  <p
                    className={`text-sm font-semibold ${
                      recentMeanRMultiple >= 0 ? "text-green-600" : "text-red-600"
                    }`}
                  >
                    {recentMeanRMultiple.toFixed(2)}
                  </p>
                </div>
              </div>

              {recentWinRate !== null && (
                <div>
                  <p className="text-xs text-muted-foreground">Win Rate</p>
                  <p className="text-sm font-semibold">
                    {(recentWinRate * 100).toFixed(1)}%
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Status Message */}
          {!modelVersion && (
            <p className="text-xs text-muted-foreground italic">
              Agent is in observe mode, collecting training data
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
