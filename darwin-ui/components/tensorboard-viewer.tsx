"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Loader2, ExternalLink, Activity, AlertCircle, RefreshCw } from "lucide-react"
import { api } from "@/lib/api-client"

interface TensorboardRun {
  run_name: string
  timestamp: string
  agent_name: string
  total_timesteps: number
  log_dir: string
}

interface TensorboardViewerProps {
  agentName: string
}

export function TensorboardViewer({ agentName }: TensorboardViewerProps) {
  const [runs, setRuns] = useState<TensorboardRun[]>([])
  const [selectedRun, setSelectedRun] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [tensorboardUrl, setTensorboardUrl] = useState<string | null>(null)

  const loadTensorboardRuns = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await api.rl.tensorboardRuns(agentName)
      setRuns(response.data.runs || [])

      // Auto-select most recent run
      if (response.data.runs && response.data.runs.length > 0) {
        setSelectedRun(response.data.runs[0].run_name)
      }
    } catch (err: any) {
      setError(err.message || "Failed to load Tensorboard runs")
    } finally {
      setLoading(false)
    }
  }

  const checkTensorboardStatus = async () => {
    try {
      const response = await api.rl.tensorboardStatus()
      setTensorboardUrl(response.data.url)
    } catch (err) {
      setTensorboardUrl(null)
    }
  }

  const startTensorboard = async () => {
    try {
      setError(null)
      const response = await api.rl.startTensorboard()
      setTensorboardUrl(response.data.url)
    } catch (err: any) {
      setError(err.message || "Failed to start Tensorboard")
    }
  }

  const stopTensorboard = async () => {
    try {
      setError(null)
      await api.rl.stopTensorboard()
      setTensorboardUrl(null)
    } catch (err: any) {
      setError(err.message || "Failed to stop Tensorboard")
    }
  }

  useEffect(() => {
    loadTensorboardRuns()
    checkTensorboardStatus()
  }, [agentName])

  const selectedRunData = runs.find((r) => r.run_name === selectedRun)

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
      {/* Tensorboard Status */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base">Tensorboard Server</CardTitle>
              <CardDescription>
                View training metrics and graphs in Tensorboard
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              {tensorboardUrl ? (
                <>
                  <Badge variant="success" className="gap-1">
                    <Activity className="h-3 w-3" />
                    Running
                  </Badge>
                  <Button
                    onClick={() => window.open(tensorboardUrl, "_blank")}
                    variant="default"
                    size="sm"
                  >
                    <ExternalLink className="h-4 w-4 mr-2" />
                    Open Tensorboard
                  </Button>
                  <Button onClick={stopTensorboard} variant="outline" size="sm">
                    Stop
                  </Button>
                </>
              ) : (
                <>
                  <Badge variant="secondary">Stopped</Badge>
                  <Button onClick={startTensorboard} variant="default" size="sm">
                    Start Tensorboard
                  </Button>
                </>
              )}
            </div>
          </div>
        </CardHeader>
        {tensorboardUrl && (
          <CardContent>
            <Alert>
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                Tensorboard is running at{" "}
                <a
                  href={tensorboardUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-mono text-sm underline"
                >
                  {tensorboardUrl}
                </a>
              </AlertDescription>
            </Alert>
          </CardContent>
        )}
      </Card>

      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Training Runs */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">Training Runs</CardTitle>
            <Button onClick={loadTensorboardRuns} variant="outline" size="sm">
              <RefreshCw className="h-4 w-4 mr-2" />
              Refresh
            </Button>
          </div>
          <CardDescription>
            Select a training run to view its metrics in Tensorboard
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {runs.length === 0 ? (
            <div className="text-center py-8">
              <p className="text-sm text-muted-foreground">
                No training runs found for this agent
              </p>
              <p className="text-xs text-muted-foreground mt-2">
                Train the agent first to generate Tensorboard logs
              </p>
            </div>
          ) : (
            <>
              <div className="flex items-center gap-4">
                <div className="flex-1">
                  <label className="text-sm font-medium">Select Training Run</label>
                  <Select value={selectedRun || undefined} onValueChange={setSelectedRun}>
                    <SelectTrigger className="mt-2">
                      <SelectValue placeholder="Select a run" />
                    </SelectTrigger>
                    <SelectContent>
                      {runs.map((run) => (
                        <SelectItem key={run.run_name} value={run.run_name}>
                          {run.run_name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {selectedRunData && (
                <Card className="border-muted">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-sm">Run Details</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Run Name:</span>
                      <span className="font-mono">{selectedRunData.run_name}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Timestamp:</span>
                      <span>
                        {new Date(selectedRunData.timestamp).toLocaleString("en-US", {
                          month: "short",
                          day: "numeric",
                          year: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Total Timesteps:</span>
                      <span>{selectedRunData.total_timesteps.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Log Directory:</span>
                      <span className="font-mono text-xs truncate max-w-[300px]">
                        {selectedRunData.log_dir}
                      </span>
                    </div>
                  </CardContent>
                </Card>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* Embedded Tensorboard */}
      {tensorboardUrl && selectedRun && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Tensorboard View</CardTitle>
            <CardDescription>
              Training metrics for {selectedRun}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="border rounded-lg overflow-hidden bg-muted">
              <iframe
                src={`${tensorboardUrl}#timeseries&run=${encodeURIComponent(selectedRun)}`}
                className="w-full h-[600px]"
                title="Tensorboard Viewer"
              />
            </div>
            <p className="text-xs text-muted-foreground mt-2">
              For full functionality, open Tensorboard in a new tab using the button above.
            </p>
          </CardContent>
        </Card>
      )}

      {/* Help Text */}
      <Card className="bg-muted/50">
        <CardHeader>
          <CardTitle className="text-sm">About Tensorboard</CardTitle>
        </CardHeader>
        <CardContent className="text-xs text-muted-foreground space-y-2">
          <p>
            Tensorboard displays PPO training metrics including:
          </p>
          <ul className="list-disc list-inside space-y-1 ml-2">
            <li><strong>Loss curves:</strong> Policy loss, value loss, entropy</li>
            <li><strong>Rewards:</strong> Episode reward mean and std dev</li>
            <li><strong>Learning stats:</strong> Learning rate, KL divergence, clip fraction</li>
            <li><strong>Policy metrics:</strong> Explained variance, value estimates</li>
          </ul>
          <p className="pt-2">
            Use these metrics to diagnose training issues, tune hyperparameters, and validate
            agent learning progress.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
