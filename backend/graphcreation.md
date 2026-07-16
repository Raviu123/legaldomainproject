 ## The Derivation Workflow (DPDP Act)                                                                                  
                                                                                                                         
    [Raw PDF] ──► Parser (india_code_dpdp.py) ──► LegalUnit Object                                                       
                                                     │                                                                   
       ┌─────────────────────────────────────────────┴─────────────────────────────────────────────┐                     
       ▼ (structure_extractor.py)                                                                 ▼ (entity_extractor.py)
    Definitions & References Extracted                                                         Concepts Extracted        
       │                                                                                           │                     
       └─────────────────────────────────────────────┬─────────────────────────────────────────────┘                     
                                                     ▼                                                                   
                                         Normalized JSON Data                                                            
                                                     │                                                                   
                                                     ▼ Graph Loader (schema.py)                                          
                                               [Neo4j Database]                                                          
    ──────                                                                                                               
  ### Step 1: Parsing Chapter and Section Structures                                                                     
                                                                                                                         
  • File: india_code_dpdp.py                                                                                             
  • How it is derived:                                                                                                   
      1. Uses pdfplumber to extract page text from the official DPDP gazette PDF.                                        
      2. Removes boilerplate gazette headers (extraordinary, part number, page numbers, date stamps) using compiled regex
      patterns in _BOILERPLATE_PATTERNS.                                                                                 
      3. A state machine parses line-by-line:                                                                            
          • Chapter Nodes: Matches lines like CHAPTER I, CHAPTER II using _CHAPTER_RE and tracks the current_chapter.    
          • Section Nodes: Matches the start of a section (e.g., 1., 2., 3.) using _SECTION_RE (r"^\s*(\d+[A-Z]?)\.\s+(. 
          *)") to extract the section number and title.                                                                  
          • Text Accumulation: Subsections (e.g. (1), (2)), clause bullet points (e.g. (a), (b)), provisos (Provided     
          that...), and explanations are accumulated under their parent section.                                         
      4. It constructs and returns a LegalUnit schema with id = "dpdp:secX" (or dpdp:preamble), chapter, article/section,
      title, and body text.                                                                                              
                                                                                                                         
  ──────                                                                                                                 
  ### Step 2: Extracting References & Definitions                                                                        
                                                                                                                         
  • File: structure_extractor.py                                                                                         
  • How it is derived:                                                                                                   
      1. Cross-References ([:REFERENCES]):                                                                               
      The function extract_cross_references searches section text using a regex pattern \bSection\s+(\d+)\b. If Section  
      16 mentions Section 6, it extracts it, normalizes it to the target node ID dpdp:sec6, and saves it to the unit's   
      references list.                                                                                                   
      2. Definitions ([:DEFINES]):                                                                                       
      Section 2 of the DPDP Act houses statutory definitions. The custom function extract_definitions_from_dpdp_sec2     
      parses the text of Section 2:                                                                                      
          • It searches for clauses using _DPDP_DEF_RE (which matches curly single quotes used in the MeitY gazette, e.g.
          (a) ‘Appellate Tribunal’ means...).                                                                            
          • Since definition text can span multiple lines, it greedily aggregates text lines until it hits the next      
          clause marker (e.g. (b)).                                                                                      
          • It strips trailing semicolons and saves each term and definition text to the unit's definitions list.        
                                                                                                                         
                                                                                                                         
  ──────                                                                                                                 
  ### Step 3: Extracting Concepts                                                                                        
                                                                                                                         
  • File: entity_extractor.py                                                                                            
  • How it is derived:                                                                                                   
      • Runs regex searches for key data protection phrases (e.g. Consent, Data Fiduciary, Personal Data) and queries the
      LLM (if enabled) to extract 3–7 core semantic themes from the text, saving them in the unit's concepts list.       
                                                                                                                         
  ──────                                                                                                                 
  ### Step 4: Building the Neo4j Nodes and Edges                                                                         
                                                                                                                         
  • File: schema.py                                                                                                      
  • How they are loaded (Two-Pass Loading):                                                                              
                                                                                                                         
  #### Pass 1: Node Merges (load_legal_unit_to_graph)                                                                    
                                                                                                                         
  1. Law Node: Checks/Creates the root node:                                                                             
    MERGE (l:Law {name: "DPDP"})                                                                                         
                                                                                                                         
  2. Chapter Node: Checks/Creates the chapter node and links it:                                                         
    MERGE (c:Chapter {id: "dpdp:chap_chapter_ii"}) ON CREATE SET c.name = "Chapter II"                                   
    MERGE (l:Law {name: "DPDP"})-[:HAS_CHAPTER]->(c)                                                                     
                                                                                                                         
  3. Article (Section) Node: Creates the article node and links it:                                                      
    MERGE (n:Article {id: "dpdp:sec2"}) ON CREATE SET n.title = "Obligations of Data Fiduciary", ...                     
    MERGE (c:Chapter {id: "dpdp:chap_chapter_ii"})-[:HAS_ARTICLE]->(n)                                                   
                                                                                                                         
  4. Definition Nodes: If definitions exist (such as inside Section 2), it creates them and links them:                  
    MERGE (d:Definition {id: "dpdp:def_personal_data"}) ON CREATE SET d.term = "personal data", d.definition = "..."     
    MERGE (a:Article {id: "dpdp:sec2"})-[:DEFINES]->(d)                                                                  
                                                                                                                         
                                                                                                                         
  #### Pass 2: Relationship Connections (load_references_and_concepts)                                                   
                                                                                                                         
  This pass runs after all nodes are created to prevent broken references:                                               
                                                                                                                         
  1. REFERENCES Edges: Loops through the references list:                                                                
    // Target is created as a stub if not yet ingested to prevent query failure                                          
    MERGE (target:Article {id: "dpdp:sec16"})                                                                            
    MERGE (source)-[:REFERENCES]->(target)                                                                               
                                                                                                                         
  2. HAS_CONCEPT Edges: Loops through the concepts list:                                                                 
    MERGE (c:Concept {name: "Consent"})                                                                                  
    MERGE (source)-[:HAS_CONCEPT]->(c)  