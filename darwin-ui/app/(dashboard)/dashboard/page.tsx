"use client"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Play, BarChart3, GitCompare, Brain } from "lucide-react"
import Link from "next/link"

export default function DashboardPage() {
  const quickLinks = [
    {
      title: "Runs",
      description: "Create and manage strategy backtests",
      icon: Play,
      href: "/runs",
      color: "text-blue-600",
    },
    {
      title: "Reports",
      description: "View performance metrics and analytics",
      icon: BarChart3,
      href: "/reports",
      color: "text-green-600",
    },
    {
      title: "Compare",
      description: "Compare multiple strategies side-by-side",
      icon: GitCompare,
      href: "/compare",
      color: "text-purple-600",
    },
    {
      title: "RL Monitoring",
      description: "Monitor RL agent performance and status",
      icon: Brain,
      href: "/rl",
      color: "text-orange-600",
    },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Dashboard</h1>
        <p className="text-muted-foreground">
          Welcome to Darwin - Your AI-powered trading strategy research platform
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
        {quickLinks.map((link) => (
          <Link key={link.href} href={link.href}>
            <Card className="hover:shadow-lg transition-shadow cursor-pointer">
              <CardHeader>
                <link.icon className={`h-8 w-8 ${link.color}`} />
                <CardTitle className="mt-4">{link.title}</CardTitle>
                <CardDescription>{link.description}</CardDescription>
              </CardHeader>
            </Card>
          </Link>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Getting Started</CardTitle>
          <CardDescription>
            Quick guide to using Darwin
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ol className="space-y-4 list-decimal list-inside">
            <li>
              <span className="font-medium">Create a Run</span>
              <p className="text-sm text-muted-foreground ml-6">
                Configure and launch a backtest with your trading strategy
              </p>
            </li>
            <li>
              <span className="font-medium">Monitor Progress</span>
              <p className="text-sm text-muted-foreground ml-6">
                Track run execution in real-time with live progress updates
              </p>
            </li>
            <li>
              <span className="font-medium">Analyze Results</span>
              <p className="text-sm text-muted-foreground ml-6">
                View detailed performance reports with metrics and visualizations
              </p>
            </li>
            <li>
              <span className="font-medium">Compare Strategies</span>
              <p className="text-sm text-muted-foreground ml-6">
                Compare multiple runs to identify the best performing strategies
              </p>
            </li>
          </ol>
        </CardContent>
      </Card>
    </div>
  )
}
