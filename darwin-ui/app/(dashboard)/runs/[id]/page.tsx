"use client"

import { useState, useEffect } from "react"
import { useParams, useRouter } from "next/navigation"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ArrowLeft, Play, Trash2, Loader2, BarChart3 } from "lucide-react"
import { api } from "@/lib/api-client"
import { formatDate } from "@/lib/utils"

interface RunDetail {
  run_id: string
  description: string
  status: string
  created_at: string
  manifest?: {
    status: string
    start_time?: string
    end_time?: string
    bars_processed?: number
    total_bars?: number
  }
  config?: any
}

const statusColors: Record<string, "default" | "warning" | "success" | "destructive" | "info"> = {
  queued: "info",
  running: "warning",
  completed: "success",
  failed: "destructive",
}

export default function RunDetailPage() {
  const params = useParams()
  const router = useRouter()
  const runId = params.id as string

  const [run, setRun] = useState<RunDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [launching, setLaunching] = useState(false)
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    loadRun()
  }, [runId])

  const loadRun = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await api.runs.get(runId)
      setRun(response.data)
    } catch (err: any) {
      setError(err.message || "Failed to load run")
    } finally {
      setLoading(false)
    }
  }

  const handleLaunch = async () => {
    if (!run) return

    try {
      setLaunching(true)
      await api.runs.launch(runId)
      // Reload run to get updated status
      await loadRun()
    } catch (err: any) {
      setError(err.message || "Failed to launch run")
    } finally {
      setLaunching(false)
    }
  }

  const handleDelete = async () => {
    if (!run || !confirm(`Are you sure you want to delete run ${runId}?`)) return

    try {
      setDeleting(true)
      await api.runs.delete(runId)
      router.push("/runs")
    } catch (err: any) {
      setError(err.message || "Failed to delete run")
      setDeleting(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (error || !run) {
    return (
      <div className="space-y-6">
        <Link href="/runs">
          <Button variant="ghost">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Runs
          </Button>
        </Link>
        <Card className="border-destructive">
          <CardContent className="pt-6">
            <p className="text-destructive">{error || "Run not found"}</p>
          </CardContent>
        </Card>
      </div>
    )
  }

  const canLaunch = run.status === "queued" || run.status === "failed"
  const canViewReport = run.status === "completed"

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <Link href="/runs">
          <Button variant="ghost">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Runs
          </Button>
        </Link>
        <div className="flex gap-2">
          {canLaunch && (
            <Button onClick={handleLaunch} disabled={launching}>
              {launching ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Play className="mr-2 h-4 w-4" />
              )}
              Launch Run
            </Button>
          )}
          {canViewReport && (
            <Link href={`/reports/${runId}`}>
              <Button variant="outline">
                <BarChart3 className="mr-2 h-4 w-4" />
                View Report
              </Button>
            </Link>
          )}
          <Button
            variant="destructive"
            onClick={handleDelete}
            disabled={deleting}
          >
            {deleting ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Trash2 className="mr-2 h-4 w-4" />
            )}
            Delete
          </Button>
        </div>
      </div>

      <div className="grid gap-6">
        {/* Run Header */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="font-mono">{run.run_id}</CardTitle>
                <CardDescription>{run.description || "No description"}</CardDescription>
              </div>
              <Badge variant={statusColors[run.status] || "default"}>
                {run.status}
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            <dl className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <dt className="text-muted-foreground">Created</dt>
                <dd className="font-medium">{formatDate(run.created_at)}</dd>
              </div>
              {run.manifest?.start_time && (
                <div>
                  <dt className="text-muted-foreground">Started</dt>
                  <dd className="font-medium">{formatDate(run.manifest.start_time)}</dd>
                </div>
              )}
              {run.manifest?.end_time && (
                <div>
                  <dt className="text-muted-foreground">Completed</dt>
                  <dd className="font-medium">{formatDate(run.manifest.end_time)}</dd>
                </div>
              )}
            </dl>
          </CardContent>
        </Card>

        {/* Progress (if running) */}
        {run.status === "running" && run.manifest && (
          <Card>
            <CardHeader>
              <CardTitle>Progress</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span>Bars Processed</span>
                  <span className="font-medium">
                    {run.manifest.bars_processed || 0} / {run.manifest.total_bars || "?"}
                  </span>
                </div>
                {run.manifest.total_bars && (
                  <div className="w-full bg-secondary rounded-full h-2">
                    <div
                      className="bg-primary h-2 rounded-full transition-all"
                      style={{
                        width: `${((run.manifest.bars_processed || 0) / run.manifest.total_bars) * 100}%`,
                      }}
                    />
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Configuration */}
        <Card>
          <CardHeader>
            <CardTitle>Configuration</CardTitle>
            <CardDescription>Run configuration details</CardDescription>
          </CardHeader>
          <CardContent>
            {run.config ? (
              <pre className="text-xs bg-muted p-4 rounded-lg overflow-auto max-h-96">
                {JSON.stringify(run.config, null, 2)}
              </pre>
            ) : (
              <p className="text-muted-foreground text-sm">No configuration available</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
