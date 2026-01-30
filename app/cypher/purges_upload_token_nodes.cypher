MATCH (n:upload_token)
WHERE n.state <> "ok"
AND n.creation_date < datetime() - duration({days:10})
DELETE n;
