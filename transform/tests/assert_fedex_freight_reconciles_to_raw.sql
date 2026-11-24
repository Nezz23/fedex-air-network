-- Every pound of FedEx freight and mail in the raw files must survive into the route fact, month by month.
with raw as (
    select make_date(cast(year as integer), cast(month as integer), 1) as month_start,
           sum(cast(freight as double)) as freight, sum(cast(mail as double)) as mail
    from {{ source('raw', 't100_segment') }}
    where unique_carrier = 'FX'
    group by 1
), fact as (
    select month_start, sum(freight_lbs) as freight, sum(mail_lbs) as mail
    from {{ ref('fct_fedex_route_month') }} group by 1
)
select coalesce(raw.month_start, fact.month_start) as month_start, raw.freight, fact.freight
from raw full join fact using (month_start)
where abs(coalesce(raw.freight, 0) - coalesce(fact.freight, 0)) > 0.5
   or abs(coalesce(raw.mail, 0) - coalesce(fact.mail, 0)) > 0.5
