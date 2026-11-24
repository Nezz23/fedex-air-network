-- Each pound leaves one airport and arrives at another, so airport throughput is exactly twice route cargo.
with a as (select month_start, sum(handled_lbs) as handled from {{ ref('fct_fedex_airport_month') }} group by 1),
     r as (select month_start, sum(freight_lbs + mail_lbs) as cargo from {{ ref('fct_fedex_route_month') }} group by 1)
select * from a join r using (month_start) where abs(handled - 2 * cargo) > 1
