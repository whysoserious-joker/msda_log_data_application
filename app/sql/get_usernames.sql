select 
case when username = '' then 'NA'
when username like '%nessus%'  then 'nessus'
 else username end as username,
from msda_log.logdata;