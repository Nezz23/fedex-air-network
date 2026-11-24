-- Peer benchmark: every carrier's freight and capacity per month, so FedEx can be compared with UPS, Atlas, etc.
select
    month_start,
    carrier,
    any_value(carrier_name)                      as carrier_name,
    sum(departures_performed)                    as departures,
    sum(payload_lbs)                             as payload_lbs,
    sum(freight_lbs)                             as freight_lbs,
    sum(mail_lbs)                                as mail_lbs,
    sum(freight_lbs + mail_lbs) filter (where is_domestic) as domestic_cargo_lbs,
    sum(freight_lbs + mail_lbs) / nullif(sum(payload_lbs), 0) as load_factor
from {{ ref('stg_t100_segment') }}
group by all
having sum(freight_lbs) > 0
