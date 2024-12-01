SELECT 
case when username = '' then 'NA'
when username like '%%nessus%%'  then 'nessus'
 else username end as username,
IFNULL(sum(size_bytes)/count(case when size_bytes>0 then size_bytes end),0) as avg_transfer_byte_size
from msda_log.logdata l 
where time between %s and %s
group by 1;