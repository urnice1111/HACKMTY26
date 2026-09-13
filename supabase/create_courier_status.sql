-- Run this once in Supabase: SQL Editor -> New query -> Run.
-- current_pos is stored as [longitude, latitude], matching the Python tuple.

create table public.courier_status (
  id bigint generated always as identity primary key,

  status text not null
    check (status in ('drop', 'pick', 'wait')),

  current_pos double precision[] not null
    check (cardinality(current_pos) = 2),

  active_orders integer not null
    check (active_orders >= 0),

  -- A JSON list of Nodes, or NULL when the simulator has not provided it yet.
  -- Example: [{"state":"pick", "order_pos":[-100.31, 25.68]}]
  points_to_visit jsonb,

  created_at timestamptz not null default now()
);
