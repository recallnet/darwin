# Darwin UI - Frontend Application

Modern web interface for the Darwin trading strategy research platform.

## Tech Stack

- **Next.js 14** - React framework with App Router
- **TypeScript** - Type safety
- **Tailwind CSS** - Utility-first CSS framework
- **NextAuth.js** - Authentication
- **SWR** - Data fetching and caching
- **Recharts** - Charting library
- **Radix UI** - Accessible component primitives
- **Lucide Icons** - Icon library

## Features

- 🔐 Team-based authentication with role management
- 📊 Run management (create, launch, monitor)
- 📈 Performance reporting with interactive charts
- 🔄 Multi-run comparison and meta-analysis
- 🤖 RL agent monitoring dashboard
- 💾 Real-time progress updates via WebSockets
- 📱 Responsive design (mobile-friendly)
- 🌙 Dark mode support

## Getting Started

### Prerequisites

- Node.js 18+ and npm/yarn
- Darwin API running on `http://localhost:8000`

### Installation

1. Install dependencies:
```bash
npm install
# or
yarn install
```

2. Create environment file:
```bash
cp .env.example .env.local
```

3. The `.env.local` file has been created with a generated secret. Update if needed:
```env
NEXTAUTH_URL=http://localhost:3001
NEXTAUTH_SECRET=<generated-secret-already-set>
NEXT_PUBLIC_API_URL=http://localhost:8000
```

To generate a new secret key (if needed):
```bash
openssl rand -base64 32
```

### Development

Start the development server:
```bash
npm run dev
# or
yarn dev
```

Open [http://localhost:3001](http://localhost:3001) in your browser.

### Build

Build for production:
```bash
npm run build
npm run start
```

## Project Structure

```
darwin-ui/
├── app/                    # Next.js App Router pages
│   ├── (auth)/            # Auth pages (login, register)
│   ├── (dashboard)/       # Protected dashboard pages
│   │   ├── dashboard/     # Dashboard home
│   │   ├── runs/          # Run management
│   │   ├── reports/       # Performance reports
│   │   ├── compare/       # Strategy comparison
│   │   ├── rl/            # RL monitoring
│   │   └── settings/      # Settings and team management
│   ├── api/               # API routes (NextAuth)
│   └── layout.tsx         # Root layout
├── components/            # React components
│   └── ui/                # Reusable UI components
├── lib/                   # Utility functions
│   ├── api-client.ts      # API client with auth
│   ├── auth-provider.tsx  # NextAuth provider
│   └── utils.ts           # Helper functions
├── types/                 # TypeScript type definitions
├── public/                # Static assets
└── middleware.ts          # Auth middleware
```

## Authentication Flow

1. User visits protected page → redirected to `/login`
2. User enters credentials → NextAuth validates with Darwin API
3. API returns access token → stored in session
4. All API requests include Bearer token in headers
5. Token expires after 24 hours → user must re-login

## API Integration

The `lib/api-client.ts` file provides a type-safe API client:

```typescript
import { api } from "@/lib/api-client"

// Example: Fetch runs
const runs = await api.runs.list({ status: "completed" })

// Example: Get report
const report = await api.reports.get("run-123")
```

All API calls automatically include authentication headers.

## Components

UI components are built with Radix UI primitives and styled with Tailwind CSS:

- `Button` - Primary actions
- `Card` - Content containers
- `Input` - Form fields
- `Label` - Form labels
- More in `components/ui/`

## Styling

The app uses Tailwind CSS with a custom design system defined in `tailwind.config.ts`. Color tokens use CSS variables defined in `app/globals.css` for easy theming.

## Contributing

See the main Darwin [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.

## License

See [LICENSE](../LICENSE).
