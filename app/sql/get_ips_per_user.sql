select 
case when username = '' then 'NA'
when username like '%nessus%'  then 'nessus'
 else username end as username,
count(distinct remote_address) as ips
from msda_log.logdata l 
group by 1;