"use client"

import { useState, useEffect } from "react"
import { useSession } from "next-auth/react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Loader2, UserPlus, Trash2, Mail, Clock, X, RefreshCw } from "lucide-react"
import { InviteModal } from "@/components/invite-modal"
import { api } from "@/lib/api-client"
import { formatDate } from "@/lib/utils"

interface TeamMember {
  user_id: string
  email: string
  name: string | null
  role: string
  joined_at: string
}

interface TeamInvitation {
  id: string
  email: string
  role: string
  invited_by: string
  invited_at: string
  expires_at: string
}

export default function MembersPage() {
  const { data: session } = useSession()
  const [members, setMembers] = useState<TeamMember[]>([])
  const [invitations, setInvitations] = useState<TeamInvitation[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showInviteModal, setShowInviteModal] = useState(false)
  const [removeDialogOpen, setRemoveDialogOpen] = useState(false)
  const [selectedMember, setSelectedMember] = useState<TeamMember | null>(null)
  const [updatingRole, setUpdatingRole] = useState<string | null>(null)

  const teamId = (session?.user as any)?.teamId

  const loadMembers = async () => {
    if (!teamId) return

    try {
      setLoading(true)
      setError(null)
      const [membersRes, invitationsRes] = await Promise.all([
        api.teams.members(teamId),
        api.teams.invitations(teamId),
      ])
      setMembers(membersRes.data.members || [])
      setInvitations(invitationsRes.data.invitations || [])
    } catch (err: any) {
      setError(err.message || "Failed to load members")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadMembers()
  }, [teamId])

  const handleInvite = async (email: string, role: string) => {
    if (!teamId) return
    await api.teams.invite(teamId, email, role)
    await loadMembers()
  }

  const handleRoleChange = async (userId: string, newRole: string) => {
    if (!teamId) return
    try {
      setUpdatingRole(userId)
      await api.teams.updateMemberRole(teamId, userId, newRole)
      await loadMembers()
    } finally {
      setUpdatingRole(null)
    }
  }

  const handleRemoveMember = async () => {
    if (!teamId || !selectedMember) return
    try {
      await api.teams.removeMember(teamId, selectedMember.user_id)
      await loadMembers()
      setRemoveDialogOpen(false)
      setSelectedMember(null)
    } catch (err: any) {
      setError(err.message || "Failed to remove member")
    }
  }

  const handleCancelInvitation = async (invitationId: string) => {
    if (!teamId) return
    try {
      await api.teams.cancelInvitation(teamId, invitationId)
      await loadMembers()
    } catch (err: any) {
      setError(err.message || "Failed to cancel invitation")
    }
  }

  const currentUserRole = members.find(
    (m) => m.user_id === (session?.user as any)?.id
  )?.role

  const isAdmin = currentUserRole === "admin"

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Team Members</h1>
          <p className="text-muted-foreground">
            Manage team members and invitations
          </p>
        </div>
        <div className="flex gap-2">
          <Button onClick={loadMembers} variant="outline">
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
          {isAdmin && (
            <Button onClick={() => setShowInviteModal(true)}>
              <UserPlus className="mr-2 h-4 w-4" />
              Invite Member
            </Button>
          )}
        </div>
      </div>

      {error && (
        <Card className="border-destructive">
          <CardContent className="pt-6">
            <p className="text-destructive">{error}</p>
          </CardContent>
        </Card>
      )}

      {/* Current Members */}
      <Card>
        <CardHeader>
          <CardTitle>Current Members ({members.length})</CardTitle>
          <CardDescription>
            Active team members with their roles and permissions
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Member</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Joined</TableHead>
                {isAdmin && <TableHead className="w-[100px]">Actions</TableHead>}
              </TableRow>
            </TableHeader>
            <TableBody>
              {members.map((member) => {
                const isCurrentUser = member.user_id === (session?.user as any)?.id
                return (
                  <TableRow key={member.user_id}>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center">
                          <span className="text-sm font-medium">
                            {(member.name || member.email)[0].toUpperCase()}
                          </span>
                        </div>
                        <span className="font-medium">{member.name || "No name"}</span>
                        {isCurrentUser && (
                          <Badge variant="secondary" className="text-xs">
                            You
                          </Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {member.email}
                    </TableCell>
                    <TableCell>
                      {isAdmin && !isCurrentUser ? (
                        <Select
                          value={member.role}
                          onValueChange={(value) => handleRoleChange(member.user_id, value)}
                          disabled={updatingRole === member.user_id}
                        >
                          <SelectTrigger className="w-[120px]">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="viewer">Viewer</SelectItem>
                            <SelectItem value="member">Member</SelectItem>
                            <SelectItem value="admin">Admin</SelectItem>
                          </SelectContent>
                        </Select>
                      ) : (
                        <Badge
                          variant={
                            member.role === "admin"
                              ? "default"
                              : member.role === "member"
                              ? "secondary"
                              : "outline"
                          }
                        >
                          {member.role}
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {formatDate(new Date(member.joined_at))}
                    </TableCell>
                    {isAdmin && (
                      <TableCell>
                        {!isCurrentUser && (
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => {
                              setSelectedMember(member)
                              setRemoveDialogOpen(true)
                            }}
                          >
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        )}
                      </TableCell>
                    )}
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Pending Invitations */}
      {isAdmin && invitations.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Pending Invitations ({invitations.length})</CardTitle>
            <CardDescription>
              Invitations waiting to be accepted
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {invitations.map((invitation) => (
                <div
                  key={invitation.id}
                  className="flex items-center justify-between p-3 border rounded-lg"
                >
                  <div className="flex items-center gap-3">
                    <Mail className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <p className="font-medium">{invitation.email}</p>
                      <div className="flex items-center gap-2 mt-1">
                        <Badge variant="outline" className="text-xs">
                          {invitation.role}
                        </Badge>
                        <p className="text-xs text-muted-foreground">
                          <Clock className="h-3 w-3 inline mr-1" />
                          Sent {formatDate(new Date(invitation.invited_at))}
                        </p>
                      </div>
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleCancelInvitation(invitation.id)}
                  >
                    <X className="h-4 w-4 mr-1" />
                    Cancel
                  </Button>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Invite Modal */}
      <InviteModal
        open={showInviteModal}
        onOpenChange={setShowInviteModal}
        onInvite={handleInvite}
      />

      {/* Remove Member Dialog */}
      <AlertDialog open={removeDialogOpen} onOpenChange={setRemoveDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove Team Member?</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to remove {selectedMember?.name || selectedMember?.email} from
              the team? They will lose access to all team data and runs.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleRemoveMember}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Remove Member
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
