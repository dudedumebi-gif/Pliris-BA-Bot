"""SQL contracts for the protected monitoring dashboard."""


class DashboardQueries:
    """Aggregate-only queries; no prompt, response, or guest identity is selected."""

    SUMMARY = """
        with response_stats as (
            select
                count(*)::int as total_responses,
                count(distinct conversation_id)::int as active_conversations,
                count(*) filter (where scope_status = 'in_scope')::int
                    as in_scope_responses,
                count(*) filter (where scope_status = 'borderline')::int
                    as borderline_responses,
                count(*) filter (where scope_status = 'out_of_scope')::int
                    as out_of_scope_responses,
                count(latency_ms)::int as latency_samples,
                avg(latency_ms)::double precision as avg_latency_ms,
                percentile_cont(0.95) within group (order by latency_ms)
                    ::double precision as p95_latency_ms,
                coalesce(sum(input_tokens), 0)::bigint as input_tokens,
                coalesce(sum(output_tokens), 0)::bigint as output_tokens,
                count(*) filter (
                    where input_tokens is not null or output_tokens is not null
                )::int as token_samples
            from public.messages
            where role = 'assistant'
              and created_at >= now() - (%s * interval '1 hour')
        ),
        feedback_stats as (
            select
                count(*)::int as feedback_records,
                count(*) filter (where rating = 1)::int as helpful_feedback,
                count(*) filter (where rating = -1)::int as unhelpful_feedback,
                count(*) filter (
                    where nullif(btrim(comment), '') is not null
                )::int as commented_feedback
            from public.user_feedback
            where created_at >= now() - (%s * interval '1 hour')
        ),
        event_stats as (
            select
                count(*) filter (
                    where event_type = 'chat.request_failed'
                )::int as request_failures,
                count(*) filter (
                    where event_type = 'chat.prompt_injection_blocked'
                )::int as prompt_injection_blocks,
                count(*) filter (
                    where event_type = 'feedback.submitted'
                )::int as feedback_submissions
            from public.monitoring_events
            where created_at >= now() - (%s * interval '1 hour')
        )
        select response_stats.*, feedback_stats.*, event_stats.*
        from response_stats
        cross join feedback_stats
        cross join event_stats
    """

    RESPONSE_TIMELINE = """
        select
            date_trunc(%s, created_at) as timestamp,
            count(*)::int as count
        from public.messages
        where role = 'assistant'
          and created_at >= now() - (%s * interval '1 hour')
        group by 1
        order by 1
    """

    SCOPE_BREAKDOWN = """
        select coalesce(scope_status, 'unknown') as name, count(*)::int as count
        from public.messages
        where role = 'assistant'
          and created_at >= now() - (%s * interval '1 hour')
        group by 1
        order by count desc, name
    """

    LATENCY_DISTRIBUTION = """
        select label, count(*)::int as count
        from (
            select
                case
                    when latency_ms < 1000 then 'Under 1s'
                    when latency_ms < 3000 then '1-3s'
                    when latency_ms < 10000 then '3-10s'
                    when latency_ms < 30000 then '10-30s'
                    else '30s+'
                end as label,
                case
                    when latency_ms < 1000 then 1
                    when latency_ms < 3000 then 2
                    when latency_ms < 10000 then 3
                    when latency_ms < 30000 then 4
                    else 5
                end as bucket_order
            from public.messages
            where role = 'assistant'
              and latency_ms is not null
              and created_at >= now() - (%s * interval '1 hour')
        ) buckets
        group by label, bucket_order
        order by bucket_order
    """

    FAILURE_BREAKDOWN = """
        select event_type as name, count(*)::int as count
        from public.monitoring_events
        where created_at >= now() - (%s * interval '1 hour')
          and (
              severity in ('error', 'critical')
              or event_type in ('chat.request_failed', 'feedback.submission_failed')
          )
        group by event_type
        order by count desc, name
    """

    MODEL_USAGE = """
        select
            coalesce(model_name, 'unrecorded') as name,
            count(*)::int as count,
            coalesce(sum(input_tokens), 0)::bigint as input_tokens,
            coalesce(sum(output_tokens), 0)::bigint as output_tokens
        from public.messages
        where role = 'assistant'
          and created_at >= now() - (%s * interval '1 hour')
        group by 1
        order by count desc, name
    """

    @staticmethod
    def bucket_for_hours(since_hours: int) -> str:
        """Use readable hourly buckets for short windows and daily buckets otherwise."""

        if type(since_hours) is not int or not 1 <= since_hours <= 720:
            raise ValueError("since_hours must be between 1 and 720")
        return "hour" if since_hours <= 48 else "day"
