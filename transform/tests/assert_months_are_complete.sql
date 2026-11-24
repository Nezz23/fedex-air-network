-- No gaps: every month between the first and last FedEx month has data.
with m as (select distinct month_start from {{ ref('fct_fedex_route_month') }}),
span as (select unnest(generate_series(min(month_start), max(month_start), interval 1 month)) as month_start from m)
select span.month_start from span left join m using (month_start) where m.month_start is null
