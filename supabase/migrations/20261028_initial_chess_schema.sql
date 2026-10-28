-- ============================================================================
-- ChessMind AI - PostgreSQL Schema Migration for Supabase
-- Tables: profiles, games, game_moves, game_analysis
-- Security: Row Level Security (RLS) with strict auth.uid() ownership checks
-- ============================================================================

-- 1. Profiles Table (extending auth.users)
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    display_name TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- Trigger to automatically create a profile row whenever a new user signs up
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (id, display_name, created_at)
    VALUES (
        new.id,
        COALESCE(new.raw_user_meta_data->>'display_name', split_part(new.email, '@', 1)),
        timezone('utc'::text, now())
    )
    ON CONFLICT (id) DO NOTHING;
    RETURN new;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Drop trigger if already exists and recreate
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();


-- 2. Games Table
CREATE TABLE IF NOT EXISTS public.games (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE DEFAULT auth.uid(),
    player_colour TEXT NOT NULL CHECK (player_colour IN ('white', 'black')),
    opponent_type TEXT NOT NULL DEFAULT 'medium', -- 'easy', 'medium', 'master', 'neural', 'human'
    result TEXT NOT NULL DEFAULT '*' CHECK (result IN ('1-0', '0-1', '1/2-1/2', '*')),
    starting_fen TEXT NOT NULL DEFAULT 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
    current_fen TEXT NOT NULL DEFAULT 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
    pgn TEXT NOT NULL DEFAULT '',
    title TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- Trigger to update updated_at on games modification
CREATE OR REPLACE FUNCTION public.handle_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    new.updated_at = timezone('utc'::text, now());
    RETURN new;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_games_updated_at ON public.games;
CREATE TRIGGER set_games_updated_at
    BEFORE UPDATE ON public.games
    FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();


-- 3. Game Moves Table
CREATE TABLE IF NOT EXISTS public.game_moves (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    game_id UUID NOT NULL REFERENCES public.games(id) ON DELETE CASCADE,
    move_number INTEGER NOT NULL,
    san TEXT NOT NULL,
    uci TEXT NOT NULL,
    fen_after_move TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);


-- 4. Game Analysis Table
CREATE TABLE IF NOT EXISTS public.game_analysis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    game_id UUID NOT NULL REFERENCES public.games(id) ON DELETE CASCADE,
    best_move TEXT NOT NULL,
    evaluation_score NUMERIC NOT NULL DEFAULT 0.0,
    search_depth INTEGER DEFAULT 3,
    analysis_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);


-- Indexes for high-performance querying
CREATE INDEX IF NOT EXISTS idx_games_user_id ON public.games(user_id);
CREATE INDEX IF NOT EXISTS idx_games_created_at ON public.games(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_game_moves_game_id ON public.game_moves(game_id, move_number ASC);
CREATE INDEX IF NOT EXISTS idx_game_analysis_game_id ON public.game_analysis(game_id);


-- ============================================================================
-- Row Level Security (RLS) Policies
-- Enforces zero-trust isolation: authenticated users only access their own data.
-- ============================================================================

-- Enable RLS on all 4 tables
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.games ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.game_moves ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.game_analysis ENABLE ROW LEVEL SECURITY;


-- Profiles RLS
DROP POLICY IF EXISTS "Users can view any profile" ON public.profiles;
CREATE POLICY "Users can view any profile"
    ON public.profiles FOR SELECT
    TO authenticated
    USING (true);

DROP POLICY IF EXISTS "Users can update their own profile" ON public.profiles;
CREATE POLICY "Users can update their own profile"
    ON public.profiles FOR UPDATE
    TO authenticated
    USING (auth.uid() = id)
    WITH CHECK (auth.uid() = id);

DROP POLICY IF EXISTS "Users can insert their own profile" ON public.profiles;
CREATE POLICY "Users can insert their own profile"
    ON public.profiles FOR INSERT
    TO authenticated
    WITH CHECK (auth.uid() = id);


-- Games RLS (strict ownership based on auth.uid())
DROP POLICY IF EXISTS "Users can view their own games" ON public.games;
CREATE POLICY "Users can view their own games"
    ON public.games FOR SELECT
    TO authenticated
    USING (user_id = auth.uid());

DROP POLICY IF EXISTS "Users can insert their own games" ON public.games;
CREATE POLICY "Users can insert their own games"
    ON public.games FOR INSERT
    TO authenticated
    WITH CHECK (user_id = auth.uid());

DROP POLICY IF EXISTS "Users can update their own games" ON public.games;
CREATE POLICY "Users can update their own games"
    ON public.games FOR UPDATE
    TO authenticated
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

DROP POLICY IF EXISTS "Users can delete their own games" ON public.games;
CREATE POLICY "Users can delete their own games"
    ON public.games FOR DELETE
    TO authenticated
    USING (user_id = auth.uid());


-- Game Moves RLS (Strict parent-game ownership validation)
-- Verifies that game_id belongs to a game owned by auth.uid().
DROP POLICY IF EXISTS "Users can view moves for their own games" ON public.game_moves;
CREATE POLICY "Users can view moves for their own games"
    ON public.game_moves FOR SELECT
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.games
            WHERE games.id = game_moves.game_id
              AND games.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS "Users can insert moves for their own games" ON public.game_moves;
CREATE POLICY "Users can insert moves for their own games"
    ON public.game_moves FOR INSERT
    TO authenticated
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.games
            WHERE games.id = game_moves.game_id
              AND games.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS "Users can update moves for their own games" ON public.game_moves;
CREATE POLICY "Users can update moves for their own games"
    ON public.game_moves FOR UPDATE
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.games
            WHERE games.id = game_moves.game_id
              AND games.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS "Users can delete moves for their own games" ON public.game_moves;
CREATE POLICY "Users can delete moves for their own games"
    ON public.game_moves FOR DELETE
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.games
            WHERE games.id = game_moves.game_id
              AND games.user_id = auth.uid()
        )
    );


-- Game Analysis RLS (Strict parent-game ownership validation)
DROP POLICY IF EXISTS "Users can view analysis for their own games" ON public.game_analysis;
CREATE POLICY "Users can view analysis for their own games"
    ON public.game_analysis FOR SELECT
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.games
            WHERE games.id = game_analysis.game_id
              AND games.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS "Users can insert analysis for their own games" ON public.game_analysis;
CREATE POLICY "Users can insert analysis for their own games"
    ON public.game_analysis FOR INSERT
    TO authenticated
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.games
            WHERE games.id = game_analysis.game_id
              AND games.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS "Users can update analysis for their own games" ON public.game_analysis;
CREATE POLICY "Users can update analysis for their own games"
    ON public.game_analysis FOR UPDATE
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.games
            WHERE games.id = game_analysis.game_id
              AND games.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS "Users can delete analysis for their own games" ON public.game_analysis;
CREATE POLICY "Users can delete analysis for their own games"
    ON public.game_analysis FOR DELETE
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.games
            WHERE games.id = game_analysis.game_id
              AND games.user_id = auth.uid()
        )
    );
