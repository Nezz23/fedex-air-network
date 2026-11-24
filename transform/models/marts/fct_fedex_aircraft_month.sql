-- FedEx flying by aircraft type and month: how hard each type is used and how full it flies.
select
    s.month_start,
    s.aircraft_type,
    coalesce(any_value(t.aircraft_name), 'Type ' || s.aircraft_type) as aircraft_name,
    sum(s.departures_performed)                    as departures,
    sum(s.ramp_to_ramp_minutes) / 60.0             as block_hours,
    sum(s.payload_lbs)                             as payload_lbs,
    sum(s.freight_lbs + s.mail_lbs)                  as cargo_lbs,
    sum(s.freight_lbs + s.mail_lbs) / nullif(sum(s.payload_lbs), 0) as load_factor,
    sum(s.payload_lbs) / nullif(sum(s.departures_performed), 0)   as avg_payload_per_departure_lbs,
    avg(s.distance_miles)                          as avg_stage_length_miles
from {{ ref('int_fedex_segment') }} s
left join {{ ref('aircraft_types') }} t on t.aircraft_type = s.aircraft_type
group by s.month_start, s.aircraft_type
