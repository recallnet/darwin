"use client"

import { useState, useEffect } from "react"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Plus, PlayCircle, Loader2 } from "lucide-react"
import { api } from "@/lib/api-client"
import { formatDate } from "@/lib/utils"

interface Run {
  run_id: string
  description: string
  status: string
  created_at: string
  symbols?: string[]
  playbooks?: string[]
}

const statusColors: Record<string, "default" | "warning" | "success" | "destructive" | "info"> = {
  queued: "info",
  running: "warning",
  completed: "success",
  failed: "destructive",
}

export default function RunsPage() {
  const [runs, setRuns] = useState<Run[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadRuns()
  }, [])

  const loadRuns = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await api.runs.list()
      setRuns(response.data.runs || [])
    } catch (err: any) {
      setError(err.message || "Failed to load runs")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Runs</h1>
          <p className="text-muted-foreground">
            Create and manage your strategy backtests
          </p>
        </div>
        <Link href="/runs/new">
          <Button>
            <Plus className="mr-2 h-4 w-4" />
            New Run
          </Button>
        </Link>
      </div>

      {error && (
        <Card className="border-destructive">
          <CardContent className="pt-6">
            <p className="text-destructive">{error}</p>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>All Runs</CardTitle>
          <CardDescription>
            View and manage your backtest runs
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : runs.length === 0 ? (
            <div className="text-center py-12">
              <PlayCircle className="mx-auto h-12 w-12 text-muted-foreground" />
              <h3 className="mt-4 text-lg font-semibold">No runs yet</h3>
              <p className="text-sm text-muted-foreground mt-2">
                Get started by creating your first backtest run
              </p>
              <Link href="/runs/new">
                <Button className="mt-4">
                  <Plus className="mr-2 h-4 w-4" />
                  Create Run
                </Button>
              </Link>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Run ID</TableHead>
                  <TableHead>Description</TableHead>
                  <TableHead>Symbols</TableHead>
                  <TableHead>Playbooks</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {runs.map((run) => (
                  <TableRow key={run.run_id}>
                    <TableCell className="font-mono text-sm">
                      {run.run_id}
                    </TableCell>
                    <TableCell>{run.description || "-"}</TableCell>
                    <TableCell>
                      {run.symbols?.join(", ") || "-"}
                    </TableCell>
                    <TableCell>
                      {run.playbooks?.join(", ") || "-"}
                    </TableCell>
                    <TableCell>
                      <Badge variant={statusColors[run.status] || "default"}>
                        {run.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatDate(run.created_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      <Link href={`/runs/${run.run_id}`}>
                        <Button variant="ghost" size="sm">
                          View
                        </Button>
                      </Link>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
