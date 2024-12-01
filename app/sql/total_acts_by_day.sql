select DATE_FORMAT(time,'%%Y-%%m-%%d') as date,
count(*) as total_acts
from msda_log.logdata l 
where time between %s and %s
group by 1
order by 1;