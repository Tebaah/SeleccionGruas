-- Route CSV: after loading supabase/data/flat.csv into staging_capacity
-- (Table editor / psql \copy / supabase db), run this in the SQL editor.
begin;

insert into crane(manufacturer,model,max_capacity_t,source_pdf)
select distinct manufacturer, model, max_capacity_t::numeric, source_pdf
from staging_capacity
on conflict (manufacturer,model) do update
  set max_capacity_t = excluded.max_capacity_t,
      source_pdf     = excluded.source_pdf;

insert into chart(crane_id,page,system,counterweight_t,boom_min,boom_max,jib_m,ballast_options)
select cr.id, s.page::int, s.system,
       nullif(s.counterweight_t,'')::numeric, nullif(s.boom_min,'')::numeric,
       nullif(s.boom_max,'')::numeric, nullif(s.jib_m,'')::numeric, s.ballast_options
from (select distinct manufacturer,model,page,system,counterweight_t,boom_min,
             boom_max,jib_m,ballast_options from staging_capacity) s
join crane cr on cr.manufacturer=s.manufacturer and cr.model=s.model
on conflict (crane_id,page) do update
  set system=excluded.system, counterweight_t=excluded.counterweight_t,
      boom_min=excluded.boom_min, boom_max=excluded.boom_max,
      jib_m=excluded.jib_m, ballast_options=excluded.ballast_options;

-- replace the capacities of the cranes present in the staging table
delete from capacity where chart_id in (
  select ch.id from chart ch join crane cr on cr.id=ch.crane_id
  where (cr.manufacturer,cr.model) in
        (select distinct manufacturer,model from staging_capacity));

insert into capacity(chart_id,radius_m,boom_m,angle_deg,footnote,capacity_t)
select ch.id, s.radius_m::numeric, nullif(s.boom_m,'')::numeric,
       nullif(s.angle_deg,'')::numeric, coalesce(s.footnote,''), s.capacity_t::numeric
from staging_capacity s
join crane cr on cr.manufacturer=s.manufacturer and cr.model=s.model
join chart ch on ch.crane_id=cr.id and ch.page=s.page::int;

truncate staging_capacity;
commit;
