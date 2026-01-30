MATCH (n:upload_token)
OPTIONAL MATCH (n)-[r]-()
WHERE n.state <> "ok"
AND n.creation_date < datetime() - duration({days:10})
DELETE r;
