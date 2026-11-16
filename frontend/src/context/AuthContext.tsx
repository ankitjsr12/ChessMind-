import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import type { User, Session } from '@supabase/supabase-js';
import { supabase, isSupabaseConfigured, testSupabaseConnection } from '../services/supabase';
import type { SupabaseConnectionStatus } from '../services/supabase';
import type { UserProfile } from '../types/database';

interface AuthContextType {
  user: User | null;
  session: Session | null;
  profile: UserProfile | null;
  loading: boolean;
  isConfigured: boolean;
  connectionStatus: SupabaseConnectionStatus;
  refreshConnection: () => Promise<SupabaseConnectionStatus>;
  signIn: (email: string, password: string) => Promise<{ error: Error | null }>;
  signUp: (
    email: string,
    password: string,
    displayName?: string
  ) => Promise<{ error: Error | null; user: User | null; confirmationRequired?: boolean }>;
  signOut: () => Promise<void>;
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  session: null,
  profile: null,
  loading: true,
  isConfigured: isSupabaseConfigured,
  connectionStatus: isSupabaseConfigured ? 'syncing' : 'not_configured',
  refreshConnection: async () => (isSupabaseConfigured ? 'connected' : 'not_configured'),
  signIn: async () => ({ error: new Error('Auth not initialized') }),
  signUp: async () => ({ error: new Error('Auth not initialized'), user: null }),
  signOut: async () => {},
  refreshProfile: async () => {},
});

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [connectionStatus, setConnectionStatus] = useState<SupabaseConnectionStatus>(
    isSupabaseConfigured ? 'syncing' : 'not_configured'
  );

  // Check Supabase connectivity
  const checkConnection = useCallback(async (): Promise<SupabaseConnectionStatus> => {
    if (!isSupabaseConfigured) {
      setConnectionStatus('not_configured');
      return 'not_configured';
    }
    setConnectionStatus('syncing');
    const status = await testSupabaseConnection();
    setConnectionStatus(status);
    return status;
  }, []);

  // Fetch or populate profile record from Supabase
  const fetchProfile = useCallback(async (userId: string, userMeta?: Record<string, any>, userEmail?: string) => {
    if (!supabase) return;
    try {
      const { data, error } = await supabase
        .from('profiles')
        .select('*')
        .eq('id', userId)
        .maybeSingle();

      if (error) {
        console.warn('Error fetching profile:', error.message);
      }

      if (data) {
        setProfile(data as UserProfile);
      } else {
        // Fallback: If trigger hasn't fired yet, attempt to upsert
        const fallbackName =
          userMeta?.display_name || userEmail?.split('@')[0] || 'Player';
        const newProfile: UserProfile = {
          id: userId,
          display_name: fallbackName,
          created_at: new Date().toISOString(),
        };
        try {
          await supabase.from('profiles').upsert({
            id: userId,
            display_name: fallbackName,
          });
        } catch {
          // Ignore RLS check conflict if already exists
        }
        setProfile(newProfile);
      }
    } catch (err) {
      console.warn('Profile fetch exception:', err);
    }
  }, []);

  useEffect(() => {
    let mounted = true;

    const initAuth = async () => {
      if (!supabase) {
        if (mounted) {
          setConnectionStatus('not_configured');
          setLoading(false);
        }
        return;
      }

      try {
        // 1. Initial connectivity test
        const status = await testSupabaseConnection();
        if (mounted) setConnectionStatus(status);

        // 2. Initial Supabase session load
        const { data: { session: initialSession }, error: sessionError } = await supabase.auth.getSession();
        if (sessionError) {
          console.warn('Session error:', sessionError.message);
        }

        if (mounted) {
          setSession(initialSession);
          setUser(initialSession?.user ?? null);
          if (initialSession?.user) {
            await fetchProfile(
              initialSession.user.id,
              initialSession.user.user_metadata,
              initialSession.user.email
            );
          }
        }
      } catch (err) {
        console.warn('Auth initialization error:', err);
        if (mounted) setConnectionStatus('disconnected');
      } finally {
        if (mounted) setLoading(false);
      }
    };

    initAuth();

    // Listen to network changes
    const handleOnline = () => checkConnection();
    const handleOffline = () => setConnectionStatus('disconnected');
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    // Subscribe to Supabase auth events
    let subscription: { unsubscribe: () => void } | null = null;
    if (supabase) {
      const { data } = supabase.auth.onAuthStateChange(async (_event, newSession) => {
        if (!mounted) return;
        setSession(newSession);
        setUser(newSession?.user ?? null);
        if (newSession?.user) {
          await fetchProfile(
            newSession.user.id,
            newSession.user.user_metadata,
            newSession.user.email
          );
        } else {
          setProfile(null);
        }
        setLoading(false);
      });
      subscription = data.subscription;
    }

    return () => {
      mounted = false;
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
      if (subscription) subscription.unsubscribe();
    };
  }, [fetchProfile, checkConnection]);

  const signIn = async (email: string, password: string) => {
    if (!supabase || !isSupabaseConfigured) {
      return {
        error: new Error(
          'Supabase credentials are not configured. Please add VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY to frontend/.env.'
        ),
      };
    }

    try {
      const { data, error } = await supabase.auth.signInWithPassword({
        email: email.trim(),
        password,
      });

      if (error) {
        let msg = error.message;
        if (msg.toLowerCase().includes('invalid login credentials')) {
          msg = 'Invalid email or password. Please verify your credentials and try again.';
        } else if (msg.toLowerCase().includes('email not confirmed')) {
          msg = 'Your email address has not been confirmed. Please check your inbox or disable "Confirm email" in Supabase Dashboard.';
        }
        return { error: new Error(msg) };
      }

      if (data?.session) {
        setSession(data.session);
        setUser(data.session.user);
        await fetchProfile(
          data.session.user.id,
          data.session.user.user_metadata,
          data.session.user.email
        );
      }

      return { error: null };
    } catch (err: any) {
      return { error: new Error(err.message || 'Network error connecting to Supabase Auth.') };
    }
  };

  const signUp = async (email: string, password: string, displayName?: string) => {
    if (!supabase || !isSupabaseConfigured) {
      return {
        error: new Error(
          'Supabase credentials are not configured. Please add VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY to frontend/.env.'
        ),
        user: null,
      };
    }

    const trimmedEmail = email.trim();
    const effectiveDisplayName = (displayName?.trim() || trimmedEmail.split('@')[0]) || 'Player';

    try {
      const { data, error } = await supabase.auth.signUp({
        email: trimmedEmail,
        password,
        options: {
          data: {
            display_name: effectiveDisplayName,
          },
        },
      });

      if (error) {
        let msg = error.message;
        if (msg.toLowerCase().includes('rate limit')) {
          msg = 'Email rate limit exceeded. Please wait a few moments or disable "Confirm email" in your Supabase Dashboard (Authentication -> Providers -> Email) for immediate login without verification emails.';
        } else if (msg.toLowerCase().includes('user already registered')) {
          msg = 'An account with this email already exists. Please sign in instead.';
        }
        return { error: new Error(msg), user: null };
      }

      if (data?.user) {
        // Attempt immediate profile upsert
        try {
          await supabase.from('profiles').upsert({
            id: data.user.id,
            display_name: effectiveDisplayName,
          });
        } catch {
          // Handled by database trigger or subsequent fetchProfile
        }

        const confirmationRequired = !data.session;
        if (data.session) {
          setSession(data.session);
          setUser(data.user);
          await fetchProfile(data.user.id, data.user.user_metadata, data.user.email);
        }

        return {
          error: null,
          user: data.user,
          confirmationRequired,
        };
      }

      return { error: null, user: null };
    } catch (err: any) {
      return { error: new Error(err.message || 'Failed to communicate with Supabase Auth.'), user: null };
    }
  };

  const signOut = async () => {
    if (supabase) {
      try {
        await supabase.auth.signOut();
      } catch (err) {
        console.warn('Sign out error:', err);
      }
    }
    setUser(null);
    setSession(null);
    setProfile(null);
  };

  const refreshProfile = async () => {
    if (supabase && user) {
      await fetchProfile(user.id, user.user_metadata, user.email);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        session,
        profile,
        loading,
        isConfigured: isSupabaseConfigured,
        connectionStatus,
        refreshConnection: checkConnection,
        signIn,
        signUp,
        signOut,
        refreshProfile,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
