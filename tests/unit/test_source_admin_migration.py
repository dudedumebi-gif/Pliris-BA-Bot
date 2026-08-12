from pathlib import Path


def test_source_admin_events_are_append_only_and_protected() -> None:
    migration = Path("supabase/migrations/202607240003_add_source_admin_events.sql").read_text(
        encoding="utf-8"
    )

    assert "create table if not exists public.source_admin_events" in migration
    assert "on delete restrict" in migration
    assert "before update or delete" in migration
    assert "enable row level security" in migration
    assert "revoke all" in migration
    assert "grant select, insert" in migration


def test_hybrid_search_filters_both_branches_to_ready() -> None:
    schema = Path("supabase/migrations/202607120001_initial_pliris_schema.sql").read_text(
        encoding="utf-8"
    )

    assert schema.count("where d.status = 'ready'") >= 2
