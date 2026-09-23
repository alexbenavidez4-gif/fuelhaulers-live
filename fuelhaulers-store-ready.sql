-- fuelhaulers.live: App Store / Google Play requirements
-- (block other drivers + delete your own account)
-- Run this ONE time in Supabase: SQL Editor > New query (dropdown set to Database) > paste > Run

-- BLOCKING: a driver can hide another driver's chat messages and posts
create table public.blocks (
  user_id uuid not null default auth.uid() references public.profiles(id) on delete cascade,
  blocked_id uuid not null references public.profiles(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (user_id, blocked_id),
  check (user_id <> blocked_id)
);
alter table public.blocks enable row level security;
create policy "see own blocks" on public.blocks for select to authenticated using (user_id = auth.uid());
create policy "add own blocks" on public.blocks for insert to authenticated with check (user_id = auth.uid());
create policy "remove own blocks" on public.blocks for delete to authenticated using (user_id = auth.uid());

-- DELETE ACCOUNT: removes the driver's login, profile, and everything they posted
create or replace function public.delete_my_account() returns void
language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is null then raise exception 'Not signed in'; end if;
  delete from auth.users where id = auth.uid();
end;
$$;
revoke execute on function public.delete_my_account() from public, anon;
grant execute on function public.delete_my_account() to authenticated;

-- Let drivers remove their own memorial photos (used when deleting an account)
create policy "drivers delete own memorial photos" on storage.objects for delete to authenticated
  using (bucket_id = 'memorial' and (storage.foldername(name))[1] = auth.uid()::text);
