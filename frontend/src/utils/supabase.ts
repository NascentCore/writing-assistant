import { createClient } from '@supabase/supabase-js';
const supabaseUrl =
  process.env.SUPABASE_URL || 'https://mdzrjrkxnpzregsogpjw.supabase.co';
const supabaseAnonKey =
  process.env.SUPABASE_ANON_KEY ||
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1kenJqcmt4bnB6cmVnc29ncGp3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3MzkwODU5ODcsImV4cCI6MjA1NDY2MTk4N30.h6MeAwDm0XXCXPjLk3N3j6o2ukaauu32PlNR73hMCZY';
// Create a single supabase client for interacting with your database
const supabase = createClient(supabaseUrl, supabaseAnonKey);

export default supabase;
