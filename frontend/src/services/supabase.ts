/**
 * Supabase Client Initialization and Configuration Checker.
 *
 * Safe for client-side usage: uses only the public anon/publishable key.
 * Never import or expose the service_role key here.
 */

import { createClient } from '@supabase/supabase-js';
import type { SupabaseClient } from '@supabase/supabase-js';

const rawUrl = (import.meta.env.VITE_SUPABASE_URL as string | undefined)?.trim() ?? '';
const rawAnonKey = (import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined)?.trim() ?? '';

// Sanitize inputs (strip accidental quotes from .env formatting)
const cleanUrl = rawUrl.replace(/^["']|["']$/g, '');
const cleanAnonKey = rawAnonKey.replace(/^["']|["']$/g, '');

/**
 * Validates whether valid Supabase environment variables are present.
 */
export const isSupabaseConfigured: boolean = Boolean(
  cleanUrl &&
  cleanAnonKey &&
  cleanUrl !== '' &&
  cleanAnonKey !== '' &&
  !cleanUrl.includes('your-project-id') &&
  !cleanAnonKey.includes('your-supabase-anon-key')
);

/**
 * Singleton Supabase client instance.
 * Returns null if credentials are not yet configured.
 */
export const supabase: SupabaseClient | null = isSupabaseConfigured
  ? createClient(cleanUrl, cleanAnonKey, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: true,
      },
    })
  : null;

export type SupabaseConnectionStatus = 'connected' | 'disconnected' | 'not_configured' | 'syncing';

/**
 * Verifies live database connectivity to Supabase Cloud without exposing credentials.
 */
export async function testSupabaseConnection(): Promise<SupabaseConnectionStatus> {
  if (!isSupabaseConfigured || !supabase) {
    return 'not_configured';
  }

  try {
    // Lightweight check against public profiles table
    const { error } = await supabase.from('profiles').select('id').limit(1);
    if (error && error.code === 'PGRST301') {
      return 'disconnected';
    }
    return 'connected';
  } catch (err: any) {
    console.warn('Supabase connectivity check failed:', err?.message || err);
    return 'disconnected';
  }
}
