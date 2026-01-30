MERGE (m775:mode {mode: "-rwxrwxr-x"})
ON CREATE SET m775.numeric= 775, m775.creation_date=datetime()
ON MATCH SET m775.numeric= 775
MERGE (m755:mode {mode: "-rwxr-xr-x"})
ON CREATE SET m755.numeric= 755, m755.creation_date=datetime()
ON MATCH SET m755.numeric= 755
MERGE (m664:mode {mode: "-rw-rw-r--"})
ON CREATE SET m664.numeric= 664, m664.creation_date=datetime()
ON MATCH SET m664.numeric= 664
MERGE (m644:mode {mode: "-rw-r--r--"})
ON CREATE SET m644.numeric= 644, m644.creation_date=datetime()
ON MATCH SET m644.numeric= 644
