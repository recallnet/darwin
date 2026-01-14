"use client"

import { useState, useEffect } from "react"
import Link from "next/link"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { BarChart3, Loader2, TrendingUp, TrendingDown } from "lucide-react"
import { api } from "@/lib/api-client"
import { formatDate, formatPercent, formatCurrency } from "@/lib/utils"

interface Run {
  run_id: string
  description: string
  status: string
  created_at: string
}

export default function ReportsPage() {
  const [runs, setRuns] = useState<Run[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadCompletedRuns()
  }, [])

  const loadCompletedRuns = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await api.runs.list({ status: "completed" })
      setRuns(response.data.runs || [])
    } catch (err: any) {
      setError(err.message || "Failed to load reports")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Reports</h1>
        <p className="text-muted-foreground">
          View performance reports for completed runs
        </p>
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
          <CardTitle>Completed Runs</CardTitle>
          <CardDescription>
            Select a run to view its detailed performance report
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : runs.length === 0 ? (
            <div className="text-center py-12">
              <BarChart3 className="mx-auto h-12 w-12 text-muted-foreground" />
              <h3 className="mt-4 text-lg font-semibold">No completed runs yet</h3>
              <p className="text-sm text-muted-foreground mt-2">
                Complete a backtest run to view performance reports
              </p>
              <Link href="/runs/new">
                <Button className="mt-4">
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
                  <TableHead>Completed</TableHead>
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
                    <TableCell className="text-muted-foreground">
                      {formatDate(run.created_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      <Link href={`/reports/${run.run_id}`}>
                        <Button variant="outline" size="sm">
                          <BarChart3 className="mr-2 h-4 w-4" />
                          View Report
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
