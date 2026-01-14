"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { ArrowLeft, Loader2 } from "lucide-react"
import { api } from "@/lib/api-client"

const TIMEFRAMES = [
  { value: "15m", label: "15 Minutes" },
  { value: "1h", label: "1 Hour" },
  { value: "4h", label: "4 Hours" },
  { value: "1d", label: "1 Day" },
]

interface ModelInfo {
  value: string
  label: string
  provider: string
  description: string
}

interface PlaybookInfo {
  id: string
  name: string
  description: string
}

interface SymbolInfo {
  symbol: string
  name: string
  venue: string
}

export default function NewRunPage() {
  const router = useRouter()

  // Form state
  const [description, setDescription] = useState("")
  const [symbols, setSymbols] = useState<string[]>(["BTC-USD"])
  const [startDate, setStartDate] = useState("2024-01-01")
  const [endDate, setEndDate] = useState("2024-03-01")
  const [timeframe, setTimeframe] = useState("15m")
  const [selectedPlaybooks, setSelectedPlaybooks] = useState<string[]>(["breakout"])
  const [startingCapital, setStartingCapital] = useState(10000)
  const [llmSelection, setLlmSelection] = useState("google/gemini-3-flash")

  const [error, setError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [generatedConfig, setGeneratedConfig] = useState("")
  const [availableModels, setAvailableModels] = useState<ModelInfo[]>([])
  const [availablePlaybooks, setAvailablePlaybooks] = useState<PlaybookInfo[]>([])
  const [availableSymbols, setAvailableSymbols] = useState<SymbolInfo[]>([])
  const [loadingModels, setLoadingModels] = useState(true)
  const [loadingPlaybooks, setLoadingPlaybooks] = useState(true)
  const [loadingSymbols, setLoadingSymbols] = useState(true)

  // Fetch available options on mount
  useEffect(() => {
    const fetchData = async () => {
      // Fetch models
      try {
        const response = await api.models.list()
        setAvailableModels(response.data.models)
        if (!llmSelection && response.data.default_model) {
          setLlmSelection(response.data.default_model)
        }
      } catch (err) {
        console.error("Failed to fetch models:", err)
        setLlmSelection("google/gemini-3-flash")
      } finally {
        setLoadingModels(false)
      }

      // Fetch playbooks
      try {
        const response = await api.playbooks.list()
        setAvailablePlaybooks(response.data.playbooks)
        if (response.data.playbooks.length > 0 && selectedPlaybooks.length === 0) {
          setSelectedPlaybooks([response.data.playbooks[0].id])
        }
      } catch (err) {
        console.error("Failed to fetch playbooks:", err)
      } finally {
        setLoadingPlaybooks(false)
      }

      // Fetch symbols
      try {
        const response = await api.symbols.list()
        setAvailableSymbols(response.data.symbols)
        if (response.data.symbols.length > 0 && symbols.length === 0) {
          setSymbols([response.data.symbols[0].symbol])
        }
      } catch (err) {
        console.error("Failed to fetch symbols:", err)
      } finally {
        setLoadingSymbols(false)
      }
    }
    fetchData()
  }, [])

  // Generate JSON config whenever form values change
  useEffect(() => {
    // Parse provider and model from selection (format: "provider/model")
    const [llmProvider, llmModel] = llmSelection.split("/")

    // Generate a unique run ID from description
    const runId = description
      ? description.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') + '-' + Date.now()
      : `run-${Date.now()}`

    const config = {
      run_id: runId,
      description: description || "Unnamed Strategy Backtest",
      market_scope: {
        venue: "coinbase",
        symbols: symbols,
        primary_timeframe: timeframe,
        start_date: startDate,
        end_date: endDate,
        warmup_bars: 400,
      },
      fees: {
        maker_bps: 6.0,
        taker_bps: 12.5,
      },
      portfolio: {
        starting_equity_usd: startingCapital,
        max_positions: 999,
        max_exposure_fraction: 0.9,
        allow_leverage: false,
        position_size_method: "risk_parity",
        risk_per_trade_fraction: 0.02,
      },
      llm: {
        provider: llmProvider,
        model: llmModel,
        temperature: 0.0,
        max_tokens: 500,
        max_calls_per_minute: 50,
        max_retries: 3,
        initial_retry_delay: 1.0,
        circuit_breaker_threshold: 5,
        fallback_decision: "skip",
      },
      playbooks: selectedPlaybooks.map((name) => ({
        name,
        enabled: true,
        entry_params: {},
        stop_loss_atr: name === "breakout" ? 1.2 : 1.0,
        take_profit_atr: name === "breakout" ? 2.4 : 1.8,
        time_stop_bars: name === "breakout" ? 32 : 48,
        trailing_enabled: true,
        trailing_activation_atr: name === "breakout" ? 1.2 : 0.8,
        trailing_distance_atr: name === "breakout" ? 1.2 : 1.0,
      })),
      decision_timing: "on_close",
      fill_timing: "next_open",
      price_source: "ohlcv",
      slippage_model: "static_spread",
      feature_mode: "full",
      artifacts_dir: "artifacts",
      generate_plots: true,
      save_payloads: true,
      save_responses: true,
    }

    setGeneratedConfig(JSON.stringify(config, null, 2))
  }, [description, symbols, startDate, endDate, timeframe, selectedPlaybooks, startingCapital, llmSelection])

  const handleSymbolToggle = (symbol: string) => {
    setSymbols((prev) =>
      prev.includes(symbol)
        ? prev.filter((s) => s !== symbol)
        : [...prev, symbol]
    )
  }

  const handlePlaybookToggle = (playbookId: string) => {
    setSelectedPlaybooks((prev) =>
      prev.includes(playbookId)
        ? prev.filter((p) => p !== playbookId)
        : [...prev, playbookId]
    )
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    // Validation
    if (!description.trim()) {
      setError("Description is required")
      return
    }

    if (symbols.length === 0) {
      setError("At least one symbol is required")
      return
    }

    if (selectedPlaybooks.length === 0) {
      setError("At least one playbook must be selected")
      return
    }

    try {
      setCreating(true)
      const config = JSON.parse(generatedConfig)
      // Wrap config in the expected request format
      const response = await api.runs.create({ config })
      const runId = response.data.run_id

      // Automatically launch the run after creation
      try {
        await api.runs.launch(runId)
      } catch (launchErr) {
        console.error("Failed to launch run:", launchErr)
        // Continue anyway - user can launch manually from run detail page
      }

      router.push(`/runs/${runId}`)
    } catch (err: any) {
      // Handle Pydantic validation errors (array of error objects)
      if (Array.isArray(err.message)) {
        const errorMessages = err.message.map((e: any) =>
          `${e.loc?.join('.') || 'Field'}: ${e.msg}`
        ).join(', ')
        setError(errorMessages)
      } else if (typeof err.message === 'object') {
        setError(JSON.stringify(err.message))
      } else {
        setError(err.message || "Failed to create run")
      }
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="space-y-6">
      <Link href="/runs">
        <Button variant="ghost">
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Runs
        </Button>
      </Link>

      <div>
        <h1 className="text-3xl font-bold">Create New Run</h1>
        <p className="text-muted-foreground">
          Configure your backtest by selecting options below
        </p>
      </div>

      {error && (
        <Card className="border-destructive">
          <CardContent className="pt-6">
            <p className="text-destructive">{error}</p>
          </CardContent>
        </Card>
      )}

      <form onSubmit={handleSubmit}>
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Configuration Form */}
          <div className="space-y-6">
            {/* Description */}
            <Card>
              <CardHeader>
                <CardTitle>Description *</CardTitle>
                <CardDescription>
                  Brief description of your strategy
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Input
                  placeholder="e.g., BTC Momentum Strategy Q1 2024"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  disabled={creating}
                  required
                />
              </CardContent>
            </Card>

            {/* Market Scope */}
            <Card>
              <CardHeader>
                <CardTitle>Market Scope</CardTitle>
                <CardDescription>
                  Select symbols and timeframe
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Venue */}
                <div className="space-y-2">
                  <Label>Venue</Label>
                  <div className="rounded-md border border-input bg-muted px-3 py-2">
                    <p className="text-sm font-medium">Coinbase</p>
                  </div>
                </div>

                {/* Symbols */}
                <div className="space-y-3">
                  <Label>Symbols *</Label>
                  {loadingSymbols ? (
                    <p className="text-sm text-muted-foreground">Loading symbols...</p>
                  ) : (
                    <div className="grid grid-cols-2 gap-2">
                      {availableSymbols.map((symbolInfo) => (
                        <div key={symbolInfo.symbol} className="flex items-center space-x-2">
                          <Checkbox
                            id={symbolInfo.symbol}
                            checked={symbols.includes(symbolInfo.symbol)}
                            onCheckedChange={() => handleSymbolToggle(symbolInfo.symbol)}
                            disabled={creating}
                          />
                          <label
                            htmlFor={symbolInfo.symbol}
                            className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer"
                          >
                            {symbolInfo.symbol}
                          </label>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Date Range */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="start-date">Start Date</Label>
                    <Input
                      id="start-date"
                      type="date"
                      value={startDate}
                      onChange={(e) => setStartDate(e.target.value)}
                      disabled={creating}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="end-date">End Date</Label>
                    <Input
                      id="end-date"
                      type="date"
                      value={endDate}
                      onChange={(e) => setEndDate(e.target.value)}
                      disabled={creating}
                    />
                  </div>
                </div>

                {/* Timeframe */}
                <div className="space-y-2">
                  <Label htmlFor="timeframe">Timeframe</Label>
                  <Select value={timeframe} onValueChange={setTimeframe} disabled={creating}>
                    <SelectTrigger id="timeframe">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {TIMEFRAMES.map((tf) => (
                        <SelectItem key={tf.value} value={tf.value}>
                          {tf.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </CardContent>
            </Card>

            {/* Playbooks */}
            <Card>
              <CardHeader>
                <CardTitle>Strategy Playbooks *</CardTitle>
                <CardDescription>
                  Select which strategies to test
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {loadingPlaybooks ? (
                  <p className="text-sm text-muted-foreground">Loading playbooks...</p>
                ) : (
                  availablePlaybooks.map((playbook) => (
                    <div key={playbook.id} className="flex items-start space-x-3">
                      <Checkbox
                        id={playbook.id}
                        checked={selectedPlaybooks.includes(playbook.id)}
                        onCheckedChange={() => handlePlaybookToggle(playbook.id)}
                        disabled={creating}
                        className="mt-1"
                      />
                      <div className="flex-1">
                        <label
                          htmlFor={playbook.id}
                          className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer"
                        >
                          {playbook.name}
                        </label>
                        <p className="text-xs text-muted-foreground mt-1">
                          {playbook.description}
                        </p>
                      </div>
                    </div>
                  ))
                )}
              </CardContent>
            </Card>

            {/* LLM Configuration */}
            <Card>
              <CardHeader>
                <CardTitle>LLM Model</CardTitle>
                <CardDescription>
                  Select the AI model to use for trading decisions
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="llm-model">Model</Label>
                  <Select
                    value={llmSelection}
                    onValueChange={setLlmSelection}
                    disabled={creating || loadingModels}
                  >
                    <SelectTrigger id="llm-model">
                      <SelectValue placeholder={loadingModels ? "Loading models..." : "Select a model"} />
                    </SelectTrigger>
                    <SelectContent>
                      {availableModels.map((model) => (
                        <SelectItem key={model.value} value={model.value}>
                          {model.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>System Prompt (Read-only)</Label>
                  <pre className="w-full min-h-[300px] rounded-md border border-input bg-muted px-3 py-2 text-xs font-mono overflow-auto whitespace-pre-wrap">
{`You are a professional crypto trading system evaluating candidate trade setups.

Your role is to:
1. Assess the quality of a trade setup according to the specified playbook
2. Identify risk factors that could invalidate the setup
3. Make a binary decision: TAKE or SKIP
4. Provide a confidence score reflecting your conviction

You MUST output valid JSON only, with no additional text or explanation.

Output schema:
{
  "decision": "take" or "skip",
  "setup_quality": "A+" | "A" | "A-" | "B+" | "B" | "B-" | "C+" | "C" | "C-",
  "confidence": 0.0 to 1.0,
  "risk_flags": ["flag1", "flag2", ...],
  "notes": "Brief reasoning (1-2 sentences max)"
}

Quality grades:
- A+/A/A-: Strong setups with excellent/good/acceptable risk/reward
- B+/B/B-: Marginal setups with varying conviction levels
- C+/C/C-: Weak setups, low quality, poor risk/reward

Risk flags can include:
- crowded_longs, crowded_shorts
- late_entry, extended_move
- high_chop, weak_setup
- no_volume_confirm, low_liquidity
- regime_mismatch

Be selective. Only take A+ or A grade setups in favorable conditions.
When in doubt, skip. Capital preservation is paramount.`}
                  </pre>
                </div>
              </CardContent>
            </Card>

            {/* Starting Capital */}
            <Card>
              <CardHeader>
                <CardTitle>Starting Capital</CardTitle>
                <CardDescription>
                  Initial capital for the backtest
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Input
                  type="number"
                  min="100"
                  step="100"
                  value={startingCapital}
                  onChange={(e) => setStartingCapital(Number(e.target.value))}
                  disabled={creating}
                />
              </CardContent>
            </Card>

            {/* Submit Buttons */}
            <div className="flex gap-2">
              <Button type="submit" disabled={creating}>
                {creating ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Creating...
                  </>
                ) : (
                  "Create Run"
                )}
              </Button>
              <Link href="/runs">
                <Button type="button" variant="outline" disabled={creating}>
                  Cancel
                </Button>
              </Link>
            </div>
          </div>

          {/* Generated Config JSON */}
          <div>
            <Card className="sticky top-6">
              <CardHeader>
                <CardTitle>Generated Configuration</CardTitle>
                <CardDescription>
                  Auto-generated JSON based on your selections (immutable)
                </CardDescription>
              </CardHeader>
              <CardContent>
                <pre className="w-full min-h-[600px] rounded-md border border-input bg-muted px-3 py-2 text-xs font-mono overflow-auto">
                  {generatedConfig}
                </pre>
              </CardContent>
            </Card>
          </div>
        </div>
      </form>
    </div>
  )
}
