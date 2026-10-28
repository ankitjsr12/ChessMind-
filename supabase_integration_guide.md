# ChessMind AI - Supabase PostgreSQL & Authentication Integration Guide

## 1. Overview
ChessMind AI now integrates natively with **Supabase PostgreSQL** for permanent, secure storage of user accounts, games, move histories, and engine evaluations, secured with PostgreSQL Row Level Security (RLS).

---

## 2. Step 1: Run the Database Migration in Supabase

1. Open your [Supabase Dashboard](https://supabase.com/dashboard).
2. Select your project and navigate to **SQL Editor** (the terminal icon on the left).
3. Click **New Query**.
4. Open and copy the entire contents of [`supabase/migrations/20261028_initial_chess_schema.sql`](file:///Users/ak/project%20/chess%20predication/supabase/migrations/20261028_initial_chess_schema.sql).
5. Paste the SQL into the editor and click **Run** (or press `Cmd + Enter`).

### Schema Created:
- **`profiles`**: User metadata, automatically populated upon signup via trigger `on_auth_user_created`.
- **`games`**: Match state, player color, opponent type, current FEN, starting FEN, PGN, and result (`1-0`, `0-1`, `1/2-1/2`, `*`).
- **`game_moves`**: Step-by-step move history (SAN, UCI, FEN after move, ply index).
- **`game_analysis`**: Engine evaluations, best moves, centipawn score, search depth, and candidate alternatives.
- **Row Level Security (RLS)**: Enforces `auth.uid() = user_id` on `games` and verifies parent game ownership on `game_moves` and `game_analysis`.

---

## 3. Step 2: Configure Supabase Authentication

1. In Supabase Dashboard, navigate to **Authentication** -> **URL Configuration**.
2. Set **Site URL**:
   - Local development: `http://localhost:5173`
   - Production: `https://your-app.vercel.app`
3. Add **Redirect URLs**:
   - `http://localhost:5173/**`
   - `https://your-app.vercel.app/**`
4. Under **Authentication** -> **Providers** -> **Email**:
   - If you want users to log in immediately without waiting for confirmation emails during testing, toggle **Confirm email** off (or leave enabled for production verification).

---

## 4. Step 3: Configure Environment Variables

### A. Local Development
Create `frontend/.env.local` (or edit `frontend/.env`):
```bash
# Python FastAPI Engine Backend
VITE_API_URL=http://localhost:8000

# Supabase Credentials (from Supabase Dashboard -> Project Settings -> API)
VITE_SUPABASE_URL=https://caezrpghkazqwliefpaw.supabase.co
VITE_SUPABASE_ANON_KEY=your-actual-supabase-anon-key
```

### B. Vercel Deployment (Frontend)
In your Vercel Project -> **Settings** -> **Environment Variables**:
| Variable Name | Value | Purpose |
| :--- | :--- | :--- |
| `VITE_API_URL` | `https://chessmind-backend.onrender.com` | URL of your deployed FastAPI backend |
| `VITE_SUPABASE_URL` | `https://caezrpghkazqwliefpaw.supabase.co` | Supabase project API URL |
| `VITE_SUPABASE_ANON_KEY` | `eyJhbGciOi...` | Supabase public anon key (safe for browser) |

### C. Render Deployment (Backend)
In your Render Web Service -> **Environment**:
| Variable Name | Value | Purpose |
| :--- | :--- | :--- |
| `PORT` | `8000` | Port for Uvicorn |
| `PYTHON_VERSION` | `3.11.8` or compatible | Python runtime version |
| `SUPABASE_URL` | *(Optional)* `https://caezrpghkazqwliefpaw.supabase.co` | Backend Supabase access |
| `SUPABASE_SERVICE_ROLE_KEY`| *(Optional)* `secret...` | Strictly private backend key (never in frontend) |

---

## 5. Security Architecture
- **No Secret Exposure**: The frontend only uses the public `anon` key. Secret keys (`service_role`, database passwords) are strictly excluded from frontend code.
- **Zero-Trust RLS Policies**:
  - `games`: `user_id = auth.uid()`
  - `game_moves` & `game_analysis`: Validates parent game ownership via:
    ```sql
    EXISTS (SELECT 1 FROM games WHERE games.id = game_moves.game_id AND games.user_id = auth.uid())
    ```
  - Users cannot access, modify, or delete any other user's records even if they manipulate request parameters or game IDs.
