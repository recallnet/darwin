"use client"

import { useState, useEffect } from "react"
import { useSession } from "next-auth/react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import * as z from "zod"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Loader2, Save } from "lucide-react"
import { api } from "@/lib/api-client"

const teamSchema = z.object({
  name: z.string().min(1, "Team name is required"),
})

type TeamFormData = z.infer<typeof teamSchema>

interface TeamSettings {
  id: string
  name: string
  slug: string
  created_at: string
}

export default function TeamSettingsPage() {
  const { data: session } = useSession()
  const [currentTeam, setCurrentTeam] = useState<TeamSettings | null>(null)
  const [loading, setLoading] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const teamId = (session?.user as any)?.teamId

  const {
    register,
    handleSubmit,
    formState: { errors, isDirty },
    setValue,
  } = useForm<TeamFormData>({
    resolver: zodResolver(teamSchema),
  })

  const loadTeam = async () => {
    if (!teamId) return

    try {
      setLoading(true)
      setError(null)
      const response = await api.teams.get(teamId)
      const team = response.data
      setValue("name", team.name)
      setCurrentTeam(team)
    } catch (err: any) {
      setError(err.message || "Failed to load team settings")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadTeam()
  }, [teamId])

  const onSubmit = async (data: TeamFormData) => {
    if (!teamId) return

    try {
      setIsSubmitting(true)
      setError(null)
      await api.teams.update(teamId, data)
      await loadTeam()
      alert("Team settings saved successfully!")
    } catch (err: any) {
      setError(err.message || "Failed to update team")
    } finally {
      setIsSubmitting(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Team Settings</h1>
        <p className="text-muted-foreground">
          Manage your team's basic information
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
          <CardTitle>Team Information</CardTitle>
          <CardDescription>
            Update your team's name and settings
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="grid gap-2">
              <Label htmlFor="name">Team Name</Label>
              <Input
                id="name"
                placeholder="My Team"
                {...register("name")}
              />
              {errors.name && (
                <p className="text-sm text-destructive">{errors.name.message}</p>
              )}
            </div>

            <div className="grid gap-2">
              <Label htmlFor="slug">Team Slug</Label>
              <Input
                id="slug"
                placeholder="my-team"
                disabled
                value={currentTeam?.slug || ""}
                className="opacity-60"
              />
              <p className="text-xs text-muted-foreground">
                Team URL identifier (cannot be changed after creation)
              </p>
            </div>

            <Button type="submit" disabled={isSubmitting || !isDirty}>
              {isSubmitting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Saving...
                </>
              ) : (
                "Save Changes"
              )}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
