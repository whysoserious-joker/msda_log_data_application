select 
case when username = '' then 'NA'
when username like '%%nessus%%'  then 'nessus'
 else username end as username,
case when sender in ('Upload','Download') then sender else 'Others' end as sender ,
sum(size_bytes) as bytes_transfered
from msda_log.logdata l 
where time between %s and %s
group by 1,2
order by 1,2,3 ;