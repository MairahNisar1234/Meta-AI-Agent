# Agent Builder Frontend

Modern Next.js 15 + TypeScript frontend for the AI Agent Builder system.

## Features

- 🎨 **Animated landing page** with floating particles and gradient effects
- 💬 **Real-time streaming chat** via Server-Sent Events (SSE)
- 🛠️ **Live tool execution feedback** — see which tool is running in real-time
- 🎭 **Markdown rendering** for agent responses (bold, headers, code blocks)
- 🌙 **Dark theme** with glassmorphism UI
- ⚡ **Zero external dependencies** for UI (pure Tailwind CSS)

## Tech Stack

- **Next.js 15** (App Router)
- **TypeScript** (strict mode)
- **Tailwind CSS** (with custom animations)
- **React 19** (RC)

## Getting Started

### 1. Install dependencies

```bash
npm install
```

### 2. Start the FastAPI backend

Make sure your backend is running on `http://localhost:8000`:

```bash
cd ..
python -m uvicorn app.main:app --reload
```

### 3. Start the dev server

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

## Project Structure

```
frontend/
├── app/
│   ├── layout.tsx          # Root layout with fonts + metadata
│   ├── page.tsx            # Home page with hero + chat button
│   └── globals.css         # Custom animations + theme tokens
├── components/
│   └── ChatBot.tsx         # Animated chat panel with streaming
├── lib/
│   └── api.ts              # Typed client for FastAPI backend
└── next.config.ts          # API proxy + streaming config
```

## API Integration

The frontend connects to the FastAPI backend via:

- **POST /chat/stream** — Server-Sent Events (SSE) for real-time streaming
- **GET /health** — Health check endpoint

The `next.config.ts` proxies `/api/*` → `http://localhost:8000/*` to avoid CORS in dev.

## Environment Variables

Create a `.env.local` file if you need to override the backend URL:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

(Default is already `http://localhost:8000`, so this is optional in dev.)

## Build for Production

```bash
npm run build
npm start
```

The production build runs on port 3000 by default.

## Scripts

- `npm run dev` — Start dev server with hot reload
- `npm run build` — Build for production
- `npm start` — Run production server
- `npm run lint` — Run ESLint

## Customization

### Theme Colors

Edit the CSS variables in `app/globals.css`:

```css
:root {
  --bg:       #050510;
  --surface:  #0d0d1f;
  --accent:   #6366f1;
  --accent2:  #8b5cf6;
  --accent3:  #06b6d4;
  ...
}
```

### Animations

All animations are defined in `globals.css` with `@keyframes`. No external libraries.

---

**Built with ❤️ using Next.js 15 + TypeScript + Tailwind CSS**
