MATCH (n:ip)
WHERE coalesce(n.status, 'empty') <> 'ok'
AND n.creation_date < datetime() - duration({days:30})
DELETE n;
