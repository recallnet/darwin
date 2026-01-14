"use client"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { CheckCircle, Circle, AlertTriangle } from "lucide-react"

interface GraduationRequirement {
  name: string
  met: boolean
  current: number | null
  required: number | null
  unit: string
}

interface GraduationProgressProps {
  agentName: string
  canGraduate: boolean
  requirements: GraduationRequirement[]
  stabilityScore: number | null
  performanceVsBaseline: number | null
}

export function GraduationProgress({
  agentName,
  canGraduate,
  requirements,
  stabilityScore,
  performanceVsBaseline,
}: GraduationProgressProps) {
  const metCount = requirements.filter((r) => r.met).length
  const totalCount = requirements.length
  const progressPercent = (metCount / totalCount) * 100

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Graduation Progress</CardTitle>
            <CardDescription>
              Requirements for {agentName} to graduate from observe mode
            </CardDescription>
          </div>
          {canGraduate ? (
            <Badge variant="default" className="h-fit">
              <CheckCircle className="h-4 w-4 mr-1" />
              Ready to Graduate
            </Badge>
          ) : (
            <Badge variant="secondary" className="h-fit">
              {metCount} / {totalCount} Met
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-6">
          {/* Overall Progress */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm font-medium">Overall Progress</p>
              <p className="text-sm text-muted-foreground">{progressPercent.toFixed(0)}%</p>
            </div>
            <Progress value={progressPercent} className="h-2" />
          </div>

          {/* Requirements List */}
          <div className="space-y-3">
            {requirements.map((req, idx) => (
              <div
                key={idx}
                className={`flex items-start gap-3 p-3 rounded-lg border ${
                  req.met ? "border-green-200 bg-green-50" : "border-gray-200"
                }`}
              >
                <div className="mt-0.5">
                  {req.met ? (
                    <CheckCircle className="h-5 w-5 text-green-600" />
                  ) : (
                    <Circle className="h-5 w-5 text-gray-400" />
                  )}
                </div>
                <div className="flex-1">
                  <p className="text-sm font-medium">{req.name}</p>
                  {req.current !== null && req.required !== null && (
                    <div className="mt-1">
                      <p className="text-xs text-muted-foreground">
                        {req.current.toLocaleString()} / {req.required.toLocaleString()} {req.unit}
                      </p>
                      <Progress
                        value={Math.min((req.current / req.required) * 100, 100)}
                        className="h-1 mt-1"
                      />
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Stability & Performance */}
          {(stabilityScore !== null || performanceVsBaseline !== null) && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t">
              {stabilityScore !== null && (
                <div>
                  <p className="text-sm font-medium mb-1">Stability Score</p>
                  <div className="flex items-center gap-2">
                    <Progress value={stabilityScore * 100} className="flex-1 h-2" />
                    <p className="text-sm font-semibold w-12 text-right">
                      {(stabilityScore * 100).toFixed(0)}%
                    </p>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    Consistency of performance over time
                  </p>
                </div>
              )}

              {performanceVsBaseline !== null && (
                <div>
                  <p className="text-sm font-medium mb-1">Performance vs Baseline</p>
                  <div className="flex items-center gap-2">
                    {performanceVsBaseline >= 1.0 ? (
                      <CheckCircle className="h-4 w-4 text-green-600" />
                    ) : (
                      <AlertTriangle className="h-4 w-4 text-yellow-600" />
                    )}
                    <p
                      className={`text-sm font-semibold ${
                        performanceVsBaseline >= 1.0 ? "text-green-600" : "text-yellow-600"
                      }`}
                    >
                      {(performanceVsBaseline * 100).toFixed(1)}%
                    </p>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    {performanceVsBaseline >= 1.0
                      ? "Outperforming baseline strategy"
                      : "Not yet outperforming baseline"}
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Graduation Message */}
          {canGraduate && (
            <div className="p-3 bg-green-50 border border-green-200 rounded-lg">
              <p className="text-sm text-green-900">
                ✓ All graduation requirements met! The agent is ready to transition to active mode
                and make real trading decisions.
              </p>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
