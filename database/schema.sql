-- VoyaTrace schema. Only `visa_rules.embedding` is a vector column.
create extension if not exists vector;

create table if not exists accounts (
    id uuid primary key default gen_random_uuid(),
    username text unique not null,
    email text unique,
    password_hash text not null,
    role text not null check (role in ('user','parser','admin')),
    is_active boolean default true,
    chat_visible_to_admin boolean default false,
    created_at timestamptz default now(),
    last_login timestamptz
);

-- THE ONLY VECTOR TABLE. Parser side only.
create table if not exists visa_rules (
    id bigserial primary key,
    country text not null,
    route_group text not null,
    sub_path text,
    section_title text,
    chunk_index int not null,
    content text not null,
    embedding vector(3072) not null,
    effective_year int,
    source_url text,
    source_notes text,
    version int default 1,
    is_active boolean default true,
    created_by uuid references accounts(id) on delete set null,
    created_at timestamptz default now()
);
create index if not exists ix_visa_rules_lookup
    on visa_rules (country, route_group, sub_path) where is_active = true;

create table if not exists required_documents (
    id bigserial primary key,
    country text not null,
    route_group text not null,
    sub_path text,
    doc_type text not null,
    doc_label text not null,
    is_required boolean default true,
    evidence_label text,
    notes text,
    display_order int default 0
);
create index if not exists ix_req_docs_lookup
    on required_documents (country, route_group, sub_path);

-- Metadata only. NO bytes, NO text, NO vector.
create table if not exists user_uploads (
    id bigserial primary key,
    user_id uuid references accounts(id) on delete cascade,
    country text not null,
    route_group text not null,
    doc_type text not null,
    filename text not null,
    file_hash text not null,
    size_bytes bigint,
    mime_type text,
    uploaded_at timestamptz default now(),
    status text default 'staged'
);
create index if not exists ix_user_uploads_user on user_uploads (user_id);

-- Plain columns only.
create table if not exists check_results (
    id bigserial primary key,
    user_id uuid references accounts(id) on delete cascade,
    session_id uuid not null,
    country text not null,
    route_group text not null,
    doc_type text,
    rule_title text,
    status text not null check (status in ('PASS','FAIL','MISSING','UNKNOWN')),
    gap_value text,
    notes text,
    created_at timestamptz default now()
);
create index if not exists ix_check_results_user on check_results (user_id);

create table if not exists chat_logs (
    id bigserial primary key,
    user_id uuid references accounts(id) on delete cascade,
    user_message text,
    assistant_reply text,
    retrieved_rule_ids bigint[],
    tokens_used int,
    error text,
    content_visible_to_admin boolean default false,
    created_at timestamptz default now()
);
create index if not exists ix_chat_logs_user on chat_logs (user_id);

create table if not exists system_events (
    id bigserial primary key,
    actor_id uuid references accounts(id) on delete set null,
    event_type text not null,
    detail text,
    severity text default 'info',
    created_at timestamptz default now()
);

-- Vector search RPC (used ONLY for chatbot query embedding)
create or replace function match_visa_rules(
  query_embedding vector(3072),
  match_count int default 6,
  filter_country text default null,
  filter_route_group text default null
)
returns table (
  id bigint, country text, route_group text, sub_path text,
  section_title text, content text, chunk_index int, similarity float
)
language sql stable as $$
  select id, country, route_group, sub_path, section_title, content, chunk_index,
         1 - (embedding <=> query_embedding) as similarity
  from visa_rules
  where is_active = true
    and (filter_country is null or country = filter_country)
    and (filter_route_group is null or route_group = filter_route_group)
  order by embedding <=> query_embedding
  limit match_count;
$$;