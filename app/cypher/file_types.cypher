MERGE (t1:file_type {name:"binary"}) 
    ON CREATE SET t1.creation_date= datetime(), t1.precision = 'low'
    ON MATCH SET t1.precision = 'low'

MERGE (t3:file_type {name:"public certificate"})
    ON CREATE SET t3.creation_date= datetime(), t3.precision = 'low'
    ON MATCH SET t3.precision = 'low'
MERGE (t3)-[:is]->(t1)

MERGE (t4:file_type {name:"text", ext:"txt"})
    ON CREATE SET t4.creation_date= datetime(), t4.precision = 'low'
    ON MATCH SET t4.precision = 'low'
MERGE (t4)-[:is]->(t1)

MERGE (t5:file_type {name:"text utf8", ext:"txt"})
    ON CREATE SET t5.creation_date= datetime(), t5.precision = 'medium'
    ON MATCH SET t5.precision = 'medium',
        t5.ext= "txt"
MERGE (t5)-[:is]->(t4)

MERGE (t51:file_type {name:"command line utf8"})
    ON CREATE SET t51.creation_date= datetime(), t51.precision = 'high'
    ON MATCH SET t51.precision = 'high'
MERGE (t51)-[:is]->(t5)

MERGE (t52:file_type {name:"cypher query utf8"})
    ON CREATE SET t52.creation_date= datetime(), t52.precision = 'high'
    ON MATCH SET t52.precision = 'high',
        t52.ext= "cypher"
MERGE (t52)-[:is]->(t5)
