select 
case when username = '' then 'NA'
when username like '%%nessus%%'  then 'nessus'
 else username end as username,
sum(case when size_bytes>0 then 1 else 0 end) as transfers
from msda_log.logdata l 
where time between %s and %s
group by 1;