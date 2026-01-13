# Supported AI Gateway Models

Darwin supports **ALL models available through Vercel AI Gateway** with automatic optimization for reasoning models.

## ✅ Fully Tested Models (17 models, 34 test cases)

### Anthropic Claude (3 models)
- `anthropic/claude-sonnet-4-5` - Best for complex trading decisions
- `anthropic/claude-opus-4-5` - Most capable, highest cost
- `anthropic/claude-haiku-4-5` - Fastest, lowest cost

### OpenAI (3 models)
- `openai/gpt-4o` - Reliable, moderate cost
- `openai/gpt-4o-mini` - Fast and cheap
- `openai/o1` - **Reasoning model** (auto 4000 tokens)

### Google Gemini (4 models)
- `google/gemini-2.0-flash` - Fast and cheap (recommended default)
- `google/gemini-2.5-flash` - Latest fast model
- `google/gemini-2.5-pro` - High quality
- `google/gemini-3-pro-preview` - **Reasoning model** (auto 4000 tokens)

### DeepSeek (2 models)
- `deepseek/deepseek-v3.2` - Very cheap, good for high-volume
- `deepseek/deepseek-reasoner` - **Reasoning model** (auto 4000 tokens)

### xAI Grok (2 models)
- `xai/grok-2-vision` - Vision capabilities
- `xai/grok-4-fast-reasoning` - **Reasoning model** (auto 4000 tokens)

### Mistral (2 models)
- `mistral/pixtral-large-latest` - Large model with vision
- `mistral/ministral-8b-latest` - Small, fast model

### Perplexity (1 model)
- `perplexity/sonar-pro` - Web-enhanced responses

## Automatic Optimization

### Reasoning Models
Darwin automatically detects reasoning models and increases `max_tokens` from 1000 to 4000 to accommodate thinking tokens:
- OpenAI o1
- Google Gemini 3 Pro Preview
- DeepSeek Reasoner
- xAI Grok 4 Fast Reasoning
- Any model with "reasoning", "o1", "gemini-3", "reasoner", or "grok-4" in the name

### Standard Models
All other models use the default `max_tokens=1000` which is sufficient for most trading decisions.

## Model Swapping

You can specify different models per run in your configuration:

```json
{
  "llm_config": {
    "provider": "google",
    "model": "google/gemini-2.0-flash",
    "temperature": 0.0,
    "max_tokens": 500
  }
}
```

Or override via environment:
```bash
MODEL_ID=anthropic/claude-sonnet-4-5 darwin run config.json
```

## Recommended Models by Use Case

### High-Volume Testing
- `google/gemini-2.0-flash` - Fast, cheap, good performance
- `deepseek/deepseek-v3.2` - Very cheap, high throughput

### Production Trading
- `anthropic/claude-sonnet-4-5` - Best quality, most reliable
- `openai/gpt-4o` - Very reliable, good quality

### Complex Analysis (Reasoning)
- `openai/o1` - Best reasoning model
- `google/gemini-3-pro-preview` - Good reasoning, cheaper
- `deepseek/deepseek-reasoner` - Cheap reasoning option

### Budget-Conscious
- `google/gemini-2.0-flash` - Best price/performance
- `anthropic/claude-haiku-4-5` - Fast Anthropic option
- `deepseek/deepseek-v3.2` - Cheapest option

## Testing Results

All 17 models passed 2 test cases each (34 total tests):
1. Simple response test ("Say: OK")
2. System prompt + question test

**Success Rate: 100% (34/34 tests passed)**

## Provider Coverage

- ✅ Anthropic (Claude)
- ✅ OpenAI (GPT, o1)
- ✅ Google (Gemini)
- ✅ DeepSeek
- ✅ xAI (Grok)
- ✅ Mistral
- ✅ Perplexity

## Notes

- **o1-mini**: Currently unavailable in AI Gateway (404 error)
- **Reasoning models**: Automatically get 4x more tokens (4000 vs 1000)
- **Temperature**: Reasoning models may ignore temperature settings
- **System prompts**: Work with all standard models, may be limited on reasoning models
