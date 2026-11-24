-- One row per FedEx directional route and month, summed over aircraft types and service classes.
-- Load factor = (freight + mail) / payload capacity: how full the aircraft flew by weight.
select
    month_start,
    year,
    month,
    origin,
    any_value(origin_city_name)                 as origin_city,
    dest,
    any_value(dest_city_name)                   as dest_city,
    bool_and(is_domestic)                       as is_domestic,
    sum(departures_scheduled) filter (where is_scheduled_service) as departures_scheduled,
    sum(departures_performed) filter (where is_scheduled_service) as departures_performed_scheduled_service,
    sum(departures_performed)                   as departures_performed,
    sum(payload_lbs)                            as payload_lbs,
    sum(freight_lbs)                            as freight_lbs,
    sum(mail_lbs)                               as mail_lbs,
    max(distance_miles)                         as distance_miles,
    sum(ramp_to_ramp_minutes)                   as ramp_to_ramp_minutes,
    sum(freight_lbs + mail_lbs) / nullif(sum(payload_lbs), 0)     as load_factor,
    sum((freight_lbs + mail_lbs) * distance_miles) / 2000          as revenue_ton_miles
from {{ ref('int_fedex_segment') }}
group by all
