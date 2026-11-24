-- FedEx Express (Federal Express Corporation, carrier FX) segments that actually flew or carried something.
select *
from {{ ref('stg_t100_segment') }}
where carrier = 'FX'
  and (departures_performed > 0 or freight_lbs > 0 or mail_lbs > 0)
