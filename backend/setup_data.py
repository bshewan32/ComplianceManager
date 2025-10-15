"""
Compliance Document Manager - Setup and Sample Data Loader
Run this script to set up the database with ISO 45001 sample data
"""

import sqlite3
from datetime import datetime
import os

DB_PATH = "compliance.db"

def init_database():
    """Initialize SQLite database with required tables"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Standards table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS standards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            version TEXT,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Clauses/Requirements table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clauses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            standard_id INTEGER NOT NULL,
            clause_number TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            weight REAL DEFAULT 1.0,
            parent_clause_id INTEGER,
            FOREIGN KEY (standard_id) REFERENCES standards(id),
            FOREIGN KEY (parent_clause_id) REFERENCES clauses(id)
        )
    """)
    
    # Documents table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            clause_id INTEGER NOT NULL,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_hash TEXT,
            document_type TEXT,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_scanned TIMESTAMP,
            FOREIGN KEY (clause_id) REFERENCES clauses(id)
        )
    """)
    
    # Document revisions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS document_revisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            revision_number INTEGER NOT NULL,
            file_path TEXT NOT NULL,
            file_hash TEXT NOT NULL,
            notes TEXT,
            created_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (document_id) REFERENCES documents(id)
        )
    """)
    
    # Scan history table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scan_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            standard_id INTEGER NOT NULL,
            folder_path TEXT NOT NULL,
            documents_found INTEGER DEFAULT 0,
            scan_duration REAL,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (standard_id) REFERENCES standards(id)
        )
    """)
    
    # User corrections/learning table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_corrections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_document_id INTEGER,
            corrected_document_id INTEGER NOT NULL,
            clause_id INTEGER NOT NULL,
            reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (original_document_id) REFERENCES documents(id),
            FOREIGN KEY (corrected_document_id) REFERENCES documents(id),
            FOREIGN KEY (clause_id) REFERENCES clauses(id)
        )
    """)
    
    # AI configuration table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL,
            api_key TEXT NOT NULL,
            model_name TEXT,
            is_active BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Monitored folders table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS monitored_folders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            standard_id INTEGER NOT NULL,
            folder_path TEXT NOT NULL UNIQUE,
            is_active BOOLEAN DEFAULT 1,
            last_scan TIMESTAMP,
            FOREIGN KEY (standard_id) REFERENCES standards(id)
        )
    """)
    
    conn.commit()
    conn.close()
    print("✓ Database tables created successfully")

def load_iso45001_sample():
    """Load ISO 45001 sample standard and clauses"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create ISO 45001 standard
    cursor.execute("""
        INSERT OR IGNORE INTO standards (name, version, description)
        VALUES (?, ?, ?)
    """, (
        "ISO 45001",
        "2018",
        "Occupational health and safety management systems - Requirements with guidance for use"
    ))
    
    standard_id = cursor.lastrowid
    if standard_id == 0:
        cursor.execute("SELECT id FROM standards WHERE name = ?", ("ISO 45001",))
        result = cursor.fetchone()
        standard_id = result[0] if result else None
    
    if not standard_id:
        raise Exception("Failed to create ISO 45001 standard")
    
    # ISO 45001 Clauses with realistic weights
    clauses = [
        # Context of the organization
        ("4", "Context of the Organization", "Understanding organizational context and stakeholder needs", 2.0, None),
        ("4.1", "Understanding the organization and its context", "Internal and external issues relevant to OH&S", 1.0, None),
        ("4.2", "Understanding needs and expectations of workers", "Requirements of interested parties", 1.5, None),
        ("4.3", "Determining scope of OH&S management system", "Boundaries and applicability", 2.0, None),
        ("4.4", "OH&S management system", "Establishing, implementing, maintaining and continually improving", 2.5, None),
        
        # Leadership and worker participation
        ("5", "Leadership and Worker Participation", "Top management commitment and participation", 3.0, None),
        ("5.1", "Leadership and commitment", "Top management demonstrates leadership", 2.5, None),
        ("5.2", "OH&S policy", "Establishing, implementing and maintaining policy", 3.0, None),
        ("5.3", "Organizational roles, responsibilities and authorities", "Assigning and communicating responsibilities", 2.0, None),
        ("5.4", "Consultation and participation of workers", "Processes for consultation and participation", 3.0, None),
        
        # Planning
        ("6", "Planning", "Actions to address risks and opportunities", 4.0, None),
        ("6.1", "Actions to address risks and opportunities", "General planning requirements", 4.0, None),
        ("6.1.1", "General", "Planning to address risks and opportunities", 3.0, None),
        ("6.1.2", "Hazard identification and assessment", "Processes for ongoing hazard identification", 5.0, None),
        ("6.1.3", "Determination of legal and other requirements", "Identifying and accessing legal requirements", 4.0, None),
        ("6.1.4", "Planning action", "Planning to take action on identified risks", 3.5, None),
        ("6.2", "OH&S objectives and planning to achieve them", "Setting and planning objectives", 3.0, None),
        
        # Support
        ("7", "Support", "Resources, competence, awareness, communication", 3.5, None),
        ("7.1", "Resources", "Determining and providing resources", 2.5, None),
        ("7.2", "Competence", "Determining and ensuring competence", 3.5, None),
        ("7.3", "Awareness", "Workers awareness of OH&S policy and system", 2.5, None),
        ("7.4", "Communication", "Internal and external communications", 3.0, None),
        ("7.5", "Documented information", "Creating, updating and controlling documents", 2.5, None),
        
        # Operation
        ("8", "Operation", "Operational planning and control", 4.5, None),
        ("8.1", "Operational planning and control", "Planning, implementing and controlling processes", 4.0, None),
        ("8.1.1", "General", "Operational planning requirements", 3.5, None),
        ("8.1.2", "Eliminating hazards and reducing OH&S risks", "Hierarchy of controls", 5.0, None),
        ("8.1.3", "Management of change", "Controlling planned temporary and permanent changes", 4.0, None),
        ("8.1.4", "Procurement", "Controlling procurement of products and services", 3.5, None),
        ("8.2", "Emergency preparedness and response", "Processes to prepare for and respond to emergencies", 4.5, None),
        
        # Performance evaluation
        ("9", "Performance Evaluation", "Monitoring, measurement, analysis and evaluation", 3.5, None),
        ("9.1", "Monitoring, measurement, analysis and performance evaluation", "General evaluation requirements", 3.5, None),
        ("9.1.1", "General", "Monitoring and measurement requirements", 3.0, None),
        ("9.1.2", "Evaluation of compliance", "Evaluating compliance with legal requirements", 4.0, None),
        ("9.2", "Internal audit", "Conducting internal audits", 3.5, None),
        ("9.3", "Management review", "Top management reviews of OH&S system", 3.5, None),
        
        # Improvement
        ("10", "Improvement", "Incident, nonconformity and continual improvement", 4.0, None),
        ("10.1", "General", "Determining opportunities for improvement", 3.0, None),
        ("10.2", "Incident, nonconformity and corrective action", "Responding to incidents and nonconformities", 4.5, None),
        ("10.3", "Continual improvement", "Continually improving suitability, adequacy and effectiveness", 3.5, None),
    ]
    
    # Insert clauses
    clause_map = {}
    for clause_data in clauses:
        clause_num, title, desc, weight, parent = clause_data
        
        parent_id = None
        if '.' in clause_num:
            parent_num = clause_num.rsplit('.', 1)[0]
            parent_id = clause_map.get(parent_num)
        
        cursor.execute("""
            INSERT INTO clauses (standard_id, clause_number, title, description, weight, parent_clause_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (standard_id, clause_num, title, desc, weight, parent_id))
        
        clause_map[clause_num] = cursor.lastrowid
    
    conn.commit()
    conn.close()
    
    print(f"✓ ISO 45001 standard loaded successfully with {len(clauses)} clauses")
    print(f"  Standard ID: {standard_id}")

def load_isnetworld_sample():
    """Load ISNetworld sample standard"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT OR IGNORE INTO standards (name, version, description)
        VALUES (?, ?, ?)
    """, (
        "ISNetworld",
        "2024",
        "ISNetworld contractor safety compliance requirements"
    ))
    
    standard_id = cursor.lastrowid
    if standard_id == 0:
        cursor.execute("SELECT id FROM standards WHERE name = ?", ("ISNetworld",))
        result = cursor.fetchone()
        standard_id = result[0] if result else None
    
    if not standard_id:
        raise Exception("Failed to create ISNetworld standard")
    
    # ISNetworld requirements (simplified)
    requirements = [
        ("1", "Safety Management System", "Overall safety management program", 4.0),
        ("2", "Written Safety Programs", "Required written safety programs and procedures", 4.5),
        ("3", "Training Programs", "Employee safety training and competency", 4.0),
        ("4", "Incident Management", "Accident investigation and reporting", 3.5),
        ("5", "Drug and Alcohol Program", "Substance abuse prevention program", 3.0),
        ("6", "Safety Meetings", "Regular safety meeting documentation", 2.5),
        ("7", "Equipment Inspection", "Equipment maintenance and inspection programs", 3.5),
        ("8", "Emergency Response", "Emergency action plans and procedures", 3.0),
        ("9", "Contractor Management", "Subcontractor safety management", 3.0),
        ("10", "Insurance and Compliance", "Insurance certificates and regulatory compliance", 4.0),
    ]
    
    for req_num, title, desc, weight in requirements:
        cursor.execute("""
            INSERT INTO clauses (standard_id, clause_number, title, description, weight)
            VALUES (?, ?, ?, ?, ?)
        """, (standard_id, req_num, title, desc, weight))
    
    conn.commit()
    conn.close()
    
    print(f"✓ ISNetworld standard loaded successfully with {len(requirements)} requirements")
    print(f"  Standard ID: {standard_id}")

def create_sample_folder_structure():
    """Create a sample folder structure guide"""
    folder_structure = """
Sample Folder Structure for Compliance Documents:
=================================================

/Compliance_Documents/
├── ISO_45001/
│   ├── 4_Context/
│   │   ├── 4.1_Context_Analysis.docx
│   │   ├── 4.2_Stakeholder_Register.xlsx
│   │   └── 4.3_Scope_Statement.pdf
│   ├── 5_Leadership/
│   │   ├── 5.2_OHS_Policy.pdf
│   │   ├── 5.3_Roles_Responsibilities.docx
│   │   └── 5.4_Consultation_Procedure.pdf
│   ├── 6_Planning/
│   │   ├── 6.1.2_Risk_Assessment.xlsx
│   │   ├── 6.1.2_Hazard_Register.xlsx
│   │   ├── 6.1.3_Legal_Register.xlsx
│   │   └── 6.2_Objectives_Plan.docx
│   ├── 7_Support/
│   │   ├── 7.2_Training_Matrix.xlsx
│   │   ├── 7.2_Competency_Records.pdf
│   │   └── 7.5_Document_Control_Procedure.pdf
│   ├── 8_Operation/
│   │   ├── 8.1.2_Work_Procedures/
│   │   │   ├── Hot_Work_Permit.pdf
│   │   │   ├── Confined_Space_Entry.pdf
│   │   │   └── LOTO_Procedure.pdf
│   │   └── 8.2_Emergency_Response_Plan.pdf
│   └── 9_Performance/
│       ├── 9.1_Monitoring_Records.xlsx
│       ├── 9.2_Internal_Audit_Schedule.xlsx
│       └── 9.3_Management_Review_Minutes.pdf
└── ISNetworld/
    ├── Safety_Manual.pdf
    ├── Training_Records.xlsx
    ├── Incident_Reports/
    │   └── 2024_Incidents.xlsx
    └── Insurance_Certificates/
        └── Current_Insurance.pdf

Tips for Document Naming:
- Include clause number in filename: "4.2_Stakeholder_Register.xlsx"
- Use descriptive names that match clause titles
- Keep consistent naming conventions
- Use folders to organize by major elements
"""
    print(folder_structure)

if __name__ == "__main__":
    print("=" * 60)
    print("Compliance Document Manager - Database Setup")
    print("=" * 60)
    print()
    
    # Check if database already exists
    if os.path.exists(DB_PATH):
        response = input(f"Database '{DB_PATH}' already exists. Delete and recreate? (y/n): ")
        if response.lower() == 'y':
            os.remove(DB_PATH)
            print(f"✓ Deleted existing database")
        else:
            print("Keeping existing database. Exiting.")
            exit(0)
    
    print("Loading sample data...")
    print()
    
    try:
        # Initialize database structure
        init_database()
        
        # Load sample standards
        load_iso45001_sample()
        load_isnetworld_sample()
        
        print()
        print("=" * 60)
        print("✓ Setup Complete!")
        print("=" * 60)
        print()
        print("Database created:", os.path.abspath(DB_PATH))
        print()
        print("Next Steps:")
        print("1. Start the backend server: python backend.py")
        print("2. Open the frontend in your browser")
        print("3. Go to Settings > Add New Standard (or use existing)")
        print("4. Go to Scan tab and point to your documents folder")
        print("5. View compliance score on Dashboard")
        print()
        
        # Verify database contents
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM standards")
        std_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM clauses")
        clause_count = cursor.fetchone()[0]
        conn.close()
        
        print(f"Database verification:")
        print(f"  - {std_count} standards loaded")
        print(f"  - {clause_count} clauses loaded")
        print()
        
        create_sample_folder_structure()
        
    except Exception as e:
        print()
        print("=" * 60)
        print("✗ ERROR during setup:")
        print("=" * 60)
        print(str(e))
        import traceback
        traceback.print_exc()
        print()
        print("Please check the error above and try again.")
        exit(1)