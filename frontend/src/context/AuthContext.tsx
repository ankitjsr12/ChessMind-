import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import type { User, Session } from '@supabase/supabase-js';
import { supabase, isSupabaseConfigured } from '../services/supabase';
import type { UserProfile } from '../types/database';

interface AuthContextType {
  user: User | null;
  session: Session | null;
  profile: UserProfile | null;
  loading: boolean;
  isConfigured: boolean;
  signIn: (email: string, password: string) => Promise<{ error: Error | null }>;
  signUp: (email: string, password: string, displayName?: string) => Promise<{ error: Error | null; user: User | null }>;
  signOut: () => Promise<void>;
  refreshProfile: () => Promise<void>;
}

const LOCAL_USER_KEY = 'chessmind_local_user';

const AuthContext = createContext<AuthContextType>({
  user: null,
  session: null,
  profile: null,
  loading: true,
  isConfigured: isSupabaseConfigured,
  signIn: async () => ({ error: null }),
  signUp: async () => ({ error: null, user: null }),
  signOut: async () => {},
  refreshProfile: async () => {},
});

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  // Fetch or refresh profile record from Supabase
  const fetchProfile = useCallback(async (userId: string) => {
    if (!supabase) return;
    try {
      const { data, error } = await supabase
        .from('profiles')
        .select('*')
        .eq('id', userId)
        .single();

      if (error && error.code !== 'PGRST116') {
        console.warn('Error fetching profile:', error.message);
      }
      if (data) {
        setProfile(data as UserProfile);
      }
    } catch (err) {
      console.warn('Profile fetch exception:', err);
    }
  }, []);

  useEffect(() => {
    if (supabase) {
      // 1. Initial Supabase session load
      supabase.auth.getSession().then(({ data: { session } }) => {
        setSession(session);
        setUser(session?.user ?? null);
        if (session?.user) {
          fetchProfile(session.user.id);
        }
        setLoading(false);
      });

      // 2. Listen to Supabase auth changes
      const {
        data: { subscription },
      } = supabase.auth.onAuthStateChange(async (_event, newSession) => {
        setSession(newSession);
        setUser(newSession?.user ?? null);
        if (newSession?.user) {
          await fetchProfile(newSession.user.id);
        } else {
          setProfile(null);
        }
        setLoading(false);
      });

      return () => {
        subscription.unsubscribe();
      };
    } else {
      // Offline / Local Demo fallback: restore local user from localStorage
      try {
        const raw = localStorage.getItem(LOCAL_USER_KEY);
        if (raw) {
          const parsed = JSON.parse(raw);
          setUser(parsed);
          setProfile({
            id: parsed.id,
            display_name: parsed.user_metadata?.display_name || parsed.email?.split('@')[0] || 'Local User',
            created_at: new Date().toISOString(),
          });
        }
      } catch (err) {
        console.warn('Could not read local user storage:', err);
      } finally {
        setLoading(false);
      }
    }
  }, [fetchProfile]);

  const signIn = async (email: string, password: string) => {
    if (supabase) {
      const { error } = await supabase.auth.signInWithPassword({
        email,
        password,
      });
      return { error: error ? new Error(error.message) : null };
    } else {
      // Local Mode: Log in locally
      const localId = `local-user-${Math.abs(email.split('').reduce((acc, c) => ((acc << 5) - acc) + c.charCodeAt(0), 0))}`;
      const localUser = {
        id: localId,
        email,
        app_metadata: {},
        user_metadata: {
          display_name: email.split('@')[0],
        },
        aud: 'authenticated',
        created_at: new Date().toISOString(),
      } as unknown as User;

      localStorage.setItem(LOCAL_USER_KEY, JSON.stringify(localUser));
      setUser(localUser);
      setProfile({
        id: localId,
        display_name: email.split('@')[0],
        created_at: new Date().toISOString(),
      });
      return { error: null };
    }
  };

  const signUp = async (email: string, password: string, displayName?: string) => {
    if (supabase) {
      const { data, error } = await supabase.auth.signUp({
        email,
        password,
        options: {
          data: {
            display_name: displayName || email.split('@')[0],
          },
        },
      });

      if (data?.user && displayName) {
        try {
          await supabase
            .from('profiles')
            .upsert({ id: data.user.id, display_name: displayName });
        } catch {
          // Fallback handled by DB trigger
        }
      }

      return {
        error: error ? new Error(error.message) : null,
        user: data?.user ?? null,
      };
    } else {
      // Local Mode: Register locally
      const localId = `local-user-${Date.now().toString(36)}`;
      const localUser = {
        id: localId,
        email,
        app_metadata: {},
        user_metadata: {
          display_name: displayName || email.split('@')[0],
        },
        aud: 'authenticated',
        created_at: new Date().toISOString(),
      } as unknown as User;

      localStorage.setItem(LOCAL_USER_KEY, JSON.stringify(localUser));
      setUser(localUser);
      setProfile({
        id: localId,
        display_name: displayName || email.split('@')[0],
        created_at: new Date().toISOString(),
      });
      return { error: null, user: localUser };
    }
  };

  const signOut = async () => {
    if (supabase) {
      await supabase.auth.signOut();
    } else {
      localStorage.removeItem(LOCAL_USER_KEY);
    }
    setUser(null);
    setSession(null);
    setProfile(null);
  };

  const refreshProfile = async () => {
    if (supabase && user) {
      await fetchProfile(user.id);
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
