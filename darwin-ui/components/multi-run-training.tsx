"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Checkbox } from "@/components/ui/checkbox"
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
  Play,
  AlertCircle,
  CheckCircle2,
  Database,
  TrendingUp,
  RefreshCw,
} from "lucide-react"
import { Progress } from "@/components/ui/progress"
import { api } from "@/lib/api-client"

interface RunSummary {
  run_id: string
  created_at: string
  status: string
  total_decisions: number
  decisions_with_outcomes: number
  symbols: string[]
}

interface TrainingJob {
  job_id: string
  status: "queued" | "running" | "completed" | "failed"
  progress: number
  current_step: string
  started_at: string
  completed_at: string | null
  model_path: string | null
  error: string | null
}

interface MultiRunTrainingProps {
  agentName: string
}

export function MultiRunTraining({ agentName }: MultiRunTrainingProps) {
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [selectedRuns, setSelectedRuns] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [trainingJob, setTrainingJob] = useState<TrainingJob | null>(null)
  const [totalTimesteps, setTotalTimesteps] = useState<number>(100000)

  const loadAvailableRuns = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await api.rl.availableRunsForTraining(agentName)
      setRuns(response.data.runs || [])
    } catch (err: any) {
      setError(err.message || "Failed to load available runs")
    } finally {
      setLoading(false)
    }
  }

  const toggleRunSelection = (runId: string) => {
    const newSelected = new Set(selectedRuns)
    if (newSelected.has(runId)) {
      newSelected.delete(runId)
    } else {
      newSelected.add(runId)
    }
    setSelectedRuns(newSelected)
  }

  const selectAllRuns = () => {
    if (selectedRuns.size === runs.length) {
      setSelectedRuns(new Set())
    } else {
      setSelectedRuns(new Set(runs.map((r) => r.run_id)))
    }
  }

  const startTraining = async () => {
    if (selectedRuns.size === 0) {
      setError("Please select at least one run")
      return
    }

    try {
      setError(null)
      const response = await api.rl.startMultiRunTraining({
        agent_name: agentName,
        run_ids: Array.from(selectedRuns),
        total_timesteps: totalTimesteps,
      })

      setTrainingJob(response.data.job)

      // Poll for job status
      const interval = setInterval(async () => {
        try {
          const statusResponse = await api.rl.trainingJobStatus(response.data.job.job_id)
          setTrainingJob(statusResponse.data.job)

          if (
            statusResponse.data.job.status === "completed" ||
            statusResponse.data.job.status === "failed"
          ) {
            clearInterval(interval)
          }
        } catch (err) {
          clearInterval(interval)
        }
      }, 2000)
    } catch (err: any) {
      setError(err.message || "Failed to start training")
    }
  }

  useEffect(() => {
    loadAvailableRuns()
  }, [agentName])

  const totalDecisions = runs
    .filter((r) => selectedRuns.has(r.run_id))
    .reduce((sum, r) => sum + r.total_decisions, 0)

  const totalWithOutcomes = runs
    .filter((r) => selectedRuns.has(r.run_id))
    .reduce((sum, r) => sum + r.decisions_with_outcomes, 0)

  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      {/* Info Card */}
      <Card className="bg-blue-50 border-blue-200">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <Database className="h-4 w-4" />
            Multi-Run Training
          </CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          <p>
            Train the {agentName} agent on combined data from multiple backtest runs for better
            generalization and reduced overfitting.
          </p>
          <ul className="list-disc list-inside mt-2 space-y-1 text-xs">
            <li>More diverse training data from different market conditions</li>
            <li>Larger dataset improves model performance</li>
            <li>Better handling of unseen scenarios</li>
          </ul>
        </CardContent>
      </Card>

      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Training Job Status */}
      {trainingJob && (
        <Card className={trainingJob.status === "failed" ? "border-destructive" : ""}>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">Training Job</CardTitle>
              <Badge
                variant={
                  trainingJob.status === "completed"
                    ? "success"
                    : trainingJob.status === "failed"
                    ? "destructive"
                    : "default"
                }
              >
                {trainingJob.status}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {trainingJob.status === "running" && (
              <>
                <div>
                  <div className="flex justify-between text-sm mb-2">
                    <span className="text-muted-foreground">{trainingJob.current_step}</span>
                    <span className="font-medium">{trainingJob.progress}%</span>
                  </div>
                  <Progress value={trainingJob.progress} className="h-2" />
                </div>
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Training in progress...</span>
                </div>
              </>
            )}

            {trainingJob.status === "completed" && (
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-green-600">
                  <CheckCircle2 className="h-5 w-5" />
                  <span className="font-medium">Training completed successfully!</span>
                </div>
                {trainingJob.model_path && (
                  <div className="text-sm">
                    <span className="text-muted-foreground">Model saved to:</span>
                    <code className="ml-2 text-xs bg-muted px-2 py-1 rounded">
                      {trainingJob.model_path}
                    </code>
                  </div>
                )}
                <Alert>
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription className="text-xs">
                    Update your run config to use the new model path and activate the agent.
                  </AlertDescription>
                </Alert>
              </div>
            )}

            {trainingJob.status === "failed" && trainingJob.error && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription className="text-sm">{trainingJob.error}</AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>
      )}

      {/* Training Configuration */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Training Configuration</CardTitle>
          <CardDescription>
            Configure training parameters before starting
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-2">
            <Label htmlFor="timesteps">Total Training Timesteps</Label>
            <Input
              id="timesteps"
              type="number"
              min="1000"
              max="1000000"
              step="1000"
              value={totalTimesteps}
              onChange={(e) => setTotalTimesteps(parseInt(e.target.value) || 100000)}
            />
            <p className="text-xs text-muted-foreground">
              Recommended: 100,000 - 200,000 timesteps for good convergence
            </p>
          </div>

          {selectedRuns.size > 0 && (
            <div className="grid grid-cols-3 gap-4 p-4 bg-muted rounded-lg">
              <div>
                <p className="text-xs text-muted-foreground">Selected Runs</p>
                <p className="text-2xl font-bold">{selectedRuns.size}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Total Decisions</p>
                <p className="text-2xl font-bold">{totalDecisions.toLocaleString()}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">With Outcomes</p>
                <p className="text-2xl font-bold">{totalWithOutcomes.toLocaleString()}</p>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Run Selection */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base">Select Runs</CardTitle>
              <CardDescription>
                Choose which runs to include in training
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <Button onClick={selectAllRuns} variant="outline" size="sm">
                {selectedRuns.size === runs.length ? "Deselect All" : "Select All"}
              </Button>
              <Button onClick={loadAvailableRuns} variant="outline" size="sm">
                <RefreshCw className="h-4 w-4 mr-2" />
                Refresh
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {runs.length === 0 ? (
            <div className="text-center py-8">
              <p className="text-sm text-muted-foreground">
                No runs available for training
              </p>
              <p className="text-xs text-muted-foreground mt-2">
                Run some backtests first to collect training data
              </p>
            </div>
          ) : (
            <div className="border rounded-lg">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-12">
                      <Checkbox
                        checked={selectedRuns.size === runs.length}
                        onCheckedChange={selectAllRuns}
                      />
                    </TableHead>
                    <TableHead>Run ID</TableHead>
                    <TableHead>Date</TableHead>
                    <TableHead>Symbols</TableHead>
                    <TableHead className="text-right">Decisions</TableHead>
                    <TableHead className="text-right">With Outcomes</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {runs.map((run) => (
                    <TableRow
                      key={run.run_id}
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => toggleRunSelection(run.run_id)}
                    >
                      <TableCell>
                        <Checkbox
                          checked={selectedRuns.has(run.run_id)}
                          onCheckedChange={() => toggleRunSelection(run.run_id)}
                        />
                      </TableCell>
                      <TableCell className="font-medium">{run.run_id}</TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {new Date(run.created_at).toLocaleDateString("en-US", {
                          month: "short",
                          day: "numeric",
                          year: "numeric",
                        })}
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-1 flex-wrap">
                          {run.symbols.slice(0, 3).map((symbol) => (
                            <Badge key={symbol} variant="outline" className="text-xs">
                              {symbol}
                            </Badge>
                          ))}
                          {run.symbols.length > 3 && (
                            <Badge variant="outline" className="text-xs">
                              +{run.symbols.length - 3}
                            </Badge>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="text-right">
                        {run.total_decisions.toLocaleString()}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          <span>{run.decisions_with_outcomes.toLocaleString()}</span>
                          <span className="text-xs text-muted-foreground">
                            ({((run.decisions_with_outcomes / run.total_decisions) * 100).toFixed(0)}
                            %)
                          </span>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Start Training Button */}
      {runs.length > 0 && (
        <div className="flex justify-end">
          <Button
            onClick={startTraining}
            disabled={selectedRuns.size === 0 || trainingJob?.status === "running"}
            size="lg"
          >
            {trainingJob?.status === "running" ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Training in Progress...
              </>
            ) : (
              <>
                <Play className="mr-2 h-4 w-4" />
                Start Training ({selectedRuns.size} run{selectedRuns.size !== 1 ? "s" : ""})
              </>
            )}
          </Button>
        </div>
      )}
    </div>
  )
}
