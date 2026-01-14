"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Loader2 } from "lucide-react"
import { api } from "@/lib/api-client"
import { formatDate } from "@/lib/utils"

interface Run {
  run_id: string
  description: string
  status: string
  created_at: string
}

interface RunSelectorProps {
  selectedRuns: string[]
  onSelectionChange: (runIds: string[]) => void
  maxSelection?: number
}

export function RunSelector({ selectedRuns, onSelectionChange, maxSelection }: RunSelectorProps) {
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
      const response = await api.runs.list({ status: "completed" })
      setRuns(response.data.runs || [])
    } catch (err: any) {
      setError(err.message || "Failed to load runs")
    } finally {
      setLoading(false)
    }
  }

  const handleToggle = (runId: string) => {
    if (selectedRuns.includes(runId)) {
      onSelectionChange(selectedRuns.filter((id) => id !== runId))
    } else {
      if (maxSelection && selectedRuns.length >= maxSelection) {
        return // Don't add if max reached
      }
      onSelectionChange([...selectedRuns, runId])
    }
  }

  if (loading) {
    return (
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        </CardContent>
      </Card>
    )
  }

  if (error) {
    return (
      <Card className="border-destructive">
        <CardContent className="pt-6">
          <p className="text-destructive">{error}</p>
        </CardContent>
      </Card>
    )
  }

  if (runs.length === 0) {
    return (
      <Card>
        <CardContent className="pt-6">
          <p className="text-center text-muted-foreground py-8">
            No completed runs available for comparison
          </p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Select Runs to Compare</CardTitle>
        <CardDescription>
          Choose {maxSelection ? `up to ${maxSelection}` : "multiple"} completed runs to compare
          {selectedRuns.length > 0 && ` (${selectedRuns.length} selected)`}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {runs.map((run) => {
            const isSelected = selectedRuns.includes(run.run_id)
            const isDisabled = !!(maxSelection && selectedRuns.length >= maxSelection && !isSelected)

            return (
              <div
                key={run.run_id}
                className={`flex items-start space-x-3 rounded-lg border p-3 ${
                  isDisabled ? "opacity-50" : "hover:bg-accent cursor-pointer"
                }`}
                onClick={() => !isDisabled && handleToggle(run.run_id)}
              >
                <Checkbox
                  id={run.run_id}
                  checked={isSelected}
                  onCheckedChange={() => handleToggle(run.run_id)}
                  disabled={isDisabled}
                />
                <div className="flex-1 space-y-1">
                  <Label
                    htmlFor={run.run_id}
                    className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer"
                  >
                    <span className="font-mono">{run.run_id}</span>
                  </Label>
                  <p className="text-sm text-muted-foreground">
                    {run.description || "No description"}
                  </p>
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <Badge variant="success" className="text-xs">
                      {run.status}
                    </Badge>
                    <span>•</span>
                    <span>{formatDate(run.created_at)}</span>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}
