MERGE (n:besoin {name:"besoins"})
ON CREATE SET n.creation_date = datetime()

MERGE (n1:besoin {name:"besoins corporels"})
ON CREATE SET n1.creation_date = datetime(), n1.priority = 1
ON MATCH SET n1.priority = 1
MERGE (n)-[:contains]->(n1)

MERGE (n11:besoin {name:"besoins battement cardiaque"})
ON CREATE SET n11.creation_date = datetime()
MERGE (n1)-[:contains]->(n11)

MERGE (n12:besoin {name:"besoins respirer"})
ON CREATE SET n12.creation_date = datetime()
MERGE (n1)-[:contains]->(n12)

MERGE (n13:besoin {name:"besoins boire"})
ON CREATE SET n13.creation_date = datetime()
MERGE (n1)-[:contains]->(n13)

MERGE (n14:besoin {name:"besoins manger"})
ON CREATE SET n14.creation_date = datetime()
MERGE (n1)-[:contains]->(n14)

MERGE (n15:besoin {name:"besoins dormir"})
ON CREATE SET n15.creation_date = datetime()
MERGE (n1)-[:contains]->(n15)

MERGE (n16:besoin {name:"besoins aller aux toilettes"})
ON CREATE SET n16.creation_date = datetime()
MERGE (n1)-[:contains]->(n16)

MERGE (n17:besoin {name:"besoins activité physique"})
ON CREATE SET n17.creation_date = datetime()
MERGE (n1)-[:contains]->(n17)

MERGE (n2:besoin {name:"besoins réflexes se prétéger"})
ON CREATE SET n2.creation_date = datetime(), n2.priority = 2
ON MATCH SET n2.priority = 2
MERGE (n)-[:contains]->(n2)

MERGE (n21:besoin {name:"besoins de mettre les mains pour se protéger d'un ballon"})
ON CREATE SET n21.creation_date = datetime()
MERGE (n2)-[:contains]->(n21)

MERGE (n3:besoin {name:"besoins de possession"})
ON CREATE SET n3.creation_date = datetime(), n3.priority = 3
ON MATCH SET n3.priority = 3
MERGE (n)-[:contains]->(n3)

MERGE (n31:besoin {name:"besoins d'un toit, d'une maison"})
ON CREATE SET n31.creation_date = datetime()
MERGE (n3)-[:contains]->(n31)

MERGE (n32:besoin {name:"besoins ressources, revenus, salaire"})
ON CREATE SET n32.creation_date = datetime()
MERGE (n3)-[:contains]->(n32)

MERGE (n33:besoin {name:"besoins d'avenir et de temps"})
ON CREATE SET n33.creation_date = datetime()
MERGE (n3)-[:contains]->(n33)

MERGE (n34:besoin {name:"besoins d'un capital, de posséder"})
ON CREATE SET n34.creation_date = datetime()
MERGE (n3)-[:contains]->(n34)

MERGE (n35:besoin {name:"besoins de protéger sa santé"})
ON CREATE SET n35.creation_date = datetime()
MERGE (n3)-[:contains]->(n35)

MERGE (n36:besoin {name:"besoins de protéger ses valeurs et sa moralité"})
ON CREATE SET n36.creation_date = datetime()
MERGE (n3)-[:contains]->(n36)

MERGE (n37:besoin {name:"besoins de protéger ses enfants, leurs avenir, leur santé, leur moralité"})
ON CREATE SET n37.creation_date = datetime()
MERGE (n3)-[:contains]->(n37)

MERGE (n4:besoin {name:"besoins de s'aimer"})
ON CREATE SET n4.creation_date = datetime()
MERGE (n)-[:contains]->(n4)

MERGE (n41:besoin {name:"besoins de moralité, raison d'être pour s'intégrer"})
ON CREATE SET n4.creation_date = datetime(), n41.priority = 4
ON MATCH SET n41.priority = 4
MERGE (n4)-[:contains]->(n41)

MERGE (n42:besoin {name:"besoins de prendre soin de soi, hyghiène"})
ON CREATE SET n42.creation_date = datetime(), n42.priority = 5
ON MATCH SET n42.priority = 5
MERGE (n4)-[:contains]->(n42)

MERGE (n43:besoin {name:"besoins d'aimer pour être aimé"})
ON CREATE SET n43.creation_date = datetime()
MERGE (n4)-[:contains]->(n43)

MERGE (n431:besoin {name:"besoins de comportement accepté"})
ON CREATE SET n431.creation_date = datetime(), n431.priority = 6
ON MATCH SET n431.priority = 6
MERGE (n43)-[:contains]->(n431)

MERGE (n4311:besoin {name:"besoins de spontannéité"})
ON CREATE SET n4311.creation_date = datetime()
MERGE (n431)-[:contains]->(n4311)

MERGE (n432:besoin {name:"besoins d'un style de vie"})
ON CREATE SET n432.creation_date = datetime(), n432.priority = 7
ON MATCH SET n432.priority = 7
MERGE (n43)-[:contains]->(n432)

MERGE (n433:besoin {name:"besoins de centre d'intérêt"})
ON CREATE SET n433.creation_date = datetime(), n433.priority = 8
ON MATCH SET n433.priority = 8
MERGE (n43)-[:contains]->(n433)
