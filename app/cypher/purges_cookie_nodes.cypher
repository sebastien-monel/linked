MATCH (n:cookie)
OPTIONAL MATCH (n)<-[:from]-(ut:upload_token)
WITH n, count(ut) as nb_token
WHERE nb_token = 0
AND n.creation_date < datetime() - duration({days:1})
DELETE n;
