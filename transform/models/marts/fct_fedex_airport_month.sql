-- Freight handled per airport and month (outbound + inbound), with departures out of the airport.
with legs as (
    select month_start, origin as airport, any_value(origin_city) as city, sum(departures_performed) as departures,
           sum(freight_lbs + mail_lbs) as outbound_lbs, 0 as inbound_lbs
    from {{ ref('fct_fedex_route_month') }} group by all
    union all
    select month_start, dest, any_value(dest_city), 0, 0, sum(freight_lbs + mail_lbs)
    from {{ ref('fct_fedex_route_month') }} group by all
)
select
    month_start,
    airport,
    any_value(city)                              as city,
    sum(departures)                              as departures,
    sum(outbound_lbs)                            as outbound_lbs,
    sum(inbound_lbs)                             as inbound_lbs,
    sum(outbound_lbs + inbound_lbs)              as handled_lbs
from legs
group by all
