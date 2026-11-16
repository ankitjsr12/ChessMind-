-- ============================================================================
-- ChessMind AI - PostgreSQL Schema Migration: Online Two-Player Games & Ratings
-- Migration: 20261102_online_two_player_schema.sql
-- Description: Non-destructive migration to support server-authoritative online
--              1v1 chess, room management, dual-player assignment, authoritative
--              clocks, provisional ratings, and privacy-preserving RLS.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. Extend public.games Table for Online 1v1 Play
-- ----------------------------------------------------------------------------
ALTER TABLE public.games
    ADD COLUMN IF NOT EXISTS white_player_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS black_player_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS room_code VARCHAR(16) UNIQUE,
    ADD COLUMN IF NOT EXISTS is_private BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS game_mode VARCHAR(32) NOT NULL DEFAULT 'ai',
    ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'completed',
    ADD COLUMN IF NOT EXISTS time_control_seconds INTEGER NOT NULL DEFAULT 600,
    ADD COLUMN IF NOT EXISTS increment_seconds INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS white_time_remaining_ms INTEGER,
    ADD COLUMN IF NOT EXISTS black_time_remaining_ms INTEGER,
    ADD COLUMN IF NOT EXISTS winner_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS winner_color VARCHAR(10) CHECK (winner_color IN ('white', 'black', 'draw')),
    ADD COLUMN IF NOT EXISTS termination_reason VARCHAR(64);

-- Comment documentation on columns
COMMENT ON COLUMN public.games.white_player_id IS 'auth.users ID assigned to White pieces in 1v1';
COMMENT ON COLUMN public.games.black_player_id IS 'auth.users ID assigned to Black pieces in 1v1';
COMMENT ON COLUMN public.games.room_code IS 'Unique alphanumeric code for private room invites';
COMMENT ON COLUMN public.games.is_private IS 'If TRUE, game and moves are strictly confidential to participants';
COMMENT ON COLUMN public.games.game_mode IS 'Game mode: ai, online_1v1_private, online_1v1_public';
COMMENT ON COLUMN public.games.status IS 'Lifecycle state: waiting, active, completed, aborted';
COMMENT ON COLUMN public.games.termination_reason IS 'Outcome reason: checkmate, resignation, timeout, agreed_draw, stalemate, repetition, insufficient_material, abandoned';


-- ----------------------------------------------------------------------------
-- 2. Extend public.profiles Table for Player Ratings & Competitive Records
-- ----------------------------------------------------------------------------
-- Note: Rating starts as NULL (Unrated / Provisional) until the user completes
-- rated matches. Defaulting to a fixed number like 1200 is avoided so unearned
-- ratings are never displayed.
ALTER TABLE public.profiles
    ADD COLUMN IF NOT EXISTS rating_rapid INTEGER DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS rating_blitz INTEGER DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS is_provisional_rapid BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS is_provisional_blitz BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS games_played INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS wins INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS losses INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS draws INTEGER NOT NULL DEFAULT 0;

COMMENT ON COLUMN public.profiles.rating_rapid IS 'Rapid Elo rating (NULL = unrated until provisional games played)';
COMMENT ON COLUMN public.profiles.rating_blitz IS 'Blitz Elo rating (NULL = unrated until provisional games played)';
COMMENT ON COLUMN public.profiles.is_provisional_rapid IS 'True until user completes documented provisional placement matches';
COMMENT ON COLUMN public.profiles.is_provisional_blitz IS 'True until user completes documented provisional placement matches';


-- ----------------------------------------------------------------------------
-- 3. Indexes for Query Performance & RLS Evaluation
-- ----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_games_white_player_id ON public.games(white_player_id);
CREATE INDEX IF NOT EXISTS idx_games_black_player_id ON public.games(black_player_id);
CREATE INDEX IF NOT EXISTS idx_games_room_code ON public.games(room_code);
CREATE INDEX IF NOT EXISTS idx_games_status ON public.games(status);
CREATE INDEX IF NOT EXISTS idx_games_is_private ON public.games(is_private);
CREATE INDEX IF NOT EXISTS idx_games_game_mode ON public.games(game_mode);


-- ----------------------------------------------------------------------------
-- 4. Row Level Security (RLS) Policies
-- ----------------------------------------------------------------------------
-- Privacy-Preserving Rule:
-- Private games (is_private = TRUE) are ONLY visible to participants (user_id,
-- white_player_id, black_player_id), whether active or completed.
-- Public games (is_private = FALSE) are visible to authenticated users once completed.

-- Clean up existing SELECT policy on games
DROP POLICY IF EXISTS "Users can view their own games" ON public.games;
DROP POLICY IF EXISTS "Users can view permitted games" ON public.games;

CREATE POLICY "Users can view permitted games"
    ON public.games FOR SELECT
    TO authenticated
    USING (
        user_id = (SELECT auth.uid())
        OR white_player_id = (SELECT auth.uid())
        OR black_player_id = (SELECT auth.uid())
        OR (is_private = FALSE AND status = 'completed')
    );

-- INSERT policy on games:
-- Browser clients can insert single-player AI games.
-- Online 1v1 games are inserted by the authoritative server via service_role key.
DROP POLICY IF EXISTS "Users can insert their own games" ON public.games;
CREATE POLICY "Users can insert their own games"
    ON public.games FOR INSERT
    TO authenticated
    WITH CHECK (
        user_id = (SELECT auth.uid())
        AND game_mode = 'ai'
    );

-- UPDATE policy on games:
-- Browser clients can only directly update single-player AI games.
-- Online 1v1 game results, clocks, and moves are updated strictly by the server.
DROP POLICY IF EXISTS "Users can update their own games" ON public.games;
CREATE POLICY "Users can update their own games"
    ON public.games FOR UPDATE
    TO authenticated
    USING (
        user_id = (SELECT auth.uid())
        AND game_mode = 'ai'
    )
    WITH CHECK (
        user_id = (SELECT auth.uid())
        AND game_mode = 'ai'
    );

-- DELETE policy on games:
DROP POLICY IF EXISTS "Users can delete their own games" ON public.games;
CREATE POLICY "Users can delete their own games"
    ON public.games FOR DELETE
    TO authenticated
    USING (user_id = (SELECT auth.uid()));


-- ----------------------------------------------------------------------------
-- 5. RLS Policies on game_moves
-- ----------------------------------------------------------------------------
DROP POLICY IF EXISTS "Users can view moves for their own games" ON public.game_moves;
DROP POLICY IF EXISTS "Users can view moves for permitted games" ON public.game_moves;

CREATE POLICY "Users can view moves for permitted games"
    ON public.game_moves FOR SELECT
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.games g
            WHERE g.id = game_moves.game_id
              AND (
                  g.user_id = (SELECT auth.uid())
                  OR g.white_player_id = (SELECT auth.uid())
                  OR g.black_player_id = (SELECT auth.uid())
                  OR (g.is_private = FALSE AND g.status = 'completed')
              )
        )
    );

DROP POLICY IF EXISTS "Users can insert moves for their own games" ON public.game_moves;
CREATE POLICY "Users can insert moves for their own games"
    ON public.game_moves FOR INSERT
    TO authenticated
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.games g
            WHERE g.id = game_moves.game_id
              AND g.user_id = (SELECT auth.uid())
              AND g.game_mode = 'ai'
        )
    );

