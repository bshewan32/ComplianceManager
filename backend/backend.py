"""
Compliance Document Management System - Backend
Main application file with database models, API endpoints, and core functionality
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime
import sqlite3
import json
import os
import hashlib
import shutil
from pathlib import Path
import asyncio
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from enhanced_scanner import EnhancedDocumentScanner

# Initialize FastAPI app
app = FastAPI(title="Compliance Document Manager")

# CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
DB_PATH = "compliance.db"
DOCUMENT_STORAGE = Path("./document_storage")
DOCUMENT_STORAGE.mkdir(exist_ok=True)

# ==================== Database Setup ====================

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

# ==================== Pydantic Models ====================

class StandardCreate(BaseModel):
    name: str
    version: Optional[str] = None
    description: Optional[str] = None

class ClauseCreate(BaseModel):
    standard_id: int
    clause_number: str
    title: str
    description: Optional[str] = None
    weight: float = 1.0
    parent_clause_id: Optional[int] = None

class DocumentUpload(BaseModel):
    clause_id: int
    notes: Optional[str] = None

class AIConfigCreate(BaseModel):
    provider: str
    api_key: str
    model_name: Optional[str] = None

class FolderScanRequest(BaseModel):
    standard_id: int
    folder_path: str

class ComplianceScore(BaseModel):
    standard_id: int
    overall_score: float
    total_clauses: int
    compliant_clauses: int
    missing_documents: List[Dict]
    element_scores: Dict[str, float]

class ReassignRequest(BaseModel):
    new_clause_id: int
    reason: Optional[str] = None

# ==================== Helper Functions ====================

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def calculate_file_hash(file_path: str) -> str:
    """Calculate SHA-256 hash of a file"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def get_file_type(file_path: str) -> str:
    """Determine document type from extension"""
    ext = Path(file_path).suffix.lower()
    type_map = {
        '.pdf': 'PDF',
        '.doc': 'Word',
        '.docx': 'Word',
        '.xls': 'Excel',
        '.xlsx': 'Excel',
        '.ppt': 'PowerPoint',
        '.pptx': 'PowerPoint',
        '.jpg': 'Image',
        '.jpeg': 'Image',
        '.png': 'Image'
    }
    return type_map.get(ext, 'Unknown')

# ==================== API Endpoints ====================

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    init_database()

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "Compliance Document Manager API is running"}

# Standards endpoints
@app.post("/api/standards")
async def create_standard(standard: StandardCreate):
    """Create a new compliance standard"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO standards (name, version, description) VALUES (?, ?, ?)",
            (standard.name, standard.version, standard.description)
        )
        conn.commit()
        standard_id = cursor.lastrowid
        return {"id": standard_id, "message": "Standard created successfully"}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Standard already exists")
    finally:
        conn.close()

@app.get("/api/standards")
async def get_standards():
    """Get all compliance standards"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM standards ORDER BY name")
    standards = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return standards

@app.get("/api/standards/{standard_id}")
async def get_standard(standard_id: int):
    """Get a specific standard with its clauses"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM standards WHERE id = ?", (standard_id,))
    standard = cursor.fetchone()
    
    if not standard:
        conn.close()
        raise HTTPException(status_code=404, detail="Standard not found")
    
    cursor.execute("SELECT * FROM clauses WHERE standard_id = ? ORDER BY clause_number", (standard_id,))
    clauses = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    return {"standard": dict(standard), "clauses": clauses}

# Clause endpoints
@app.post("/api/clauses")
async def create_clause(clause: ClauseCreate):
    """Create a new clause/requirement"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO clauses (standard_id, clause_number, title, description, weight, parent_clause_id)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (clause.standard_id, clause.clause_number, clause.title, clause.description, clause.weight, clause.parent_clause_id)
    )
    conn.commit()
    clause_id = cursor.lastrowid
    conn.close()
    return {"id": clause_id, "message": "Clause created successfully"}

@app.get("/api/clauses/{clause_id}/documents")
async def get_clause_documents(clause_id: int):
    """Get all documents for a specific clause"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT d.*, 
               (SELECT COUNT(*) FROM document_revisions WHERE document_id = d.id) as revision_count
        FROM documents d
        WHERE d.clause_id = ? AND d.status = 'active'
        ORDER BY d.created_at DESC
    """, (clause_id,))
    documents = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return documents

# Document scanning
@app.post("/api/scan")
async def scan_folder(scan_request: FolderScanRequest, background_tasks: BackgroundTasks):
    """Scan a folder for compliance documents"""
    if not os.path.exists(scan_request.folder_path):
        raise HTTPException(status_code=400, detail="Folder path does not exist")
    
    # Start scan in background
    background_tasks.add_task(perform_scan, scan_request.standard_id, scan_request.folder_path)
    
    return {"message": "Scan started", "folder": scan_request.folder_path}

async def perform_scan(standard_id: int, folder_path: str):
    """Perform the actual folder scan with enhanced matching"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create scan history entry
    cursor.execute(
        "INSERT INTO scan_history (standard_id, folder_path, started_at) VALUES (?, ?, ?)",
        (standard_id, folder_path, datetime.now())
    )
    scan_id = cursor.lastrowid
    conn.commit()
    
    start_time = datetime.now()
    
    # Get all clauses for this standard
    cursor.execute("SELECT id, clause_number, title, description FROM clauses WHERE standard_id = ?", (standard_id,))
    clauses = [dict(row) for row in cursor.fetchall()]
    
    # Initialize enhanced scanner
    scanner = EnhancedDocumentScanner()
    
    # Scan folder with enhanced matching
    scan_results = scanner.scan_folder(
        folder_path=folder_path,
        clauses=clauses,
        match_threshold=0.3,
        max_matches_per_doc=1  # Only best match per document
    )
    
    # Process matches and update database
    documents_added = 0
    documents_updated = 0
    
    for match in scan_results['matches']:
        file_path = match['file_path']
        file_name = match['file_name']
        file_hash = scanner.calculate_file_hash(file_path)
        file_ext = Path(file_path).suffix.lower()
        
        # Get best match (first one, already sorted by score)
        if match['clause_matches']:
            best_clause_id, best_score, match_reason = match['clause_matches'][0]
            
            # Check if document already exists
            cursor.execute(
                "SELECT id, file_hash FROM documents WHERE file_name = ? AND clause_id = ?",
                (file_name, best_clause_id)
            )
            existing_doc = cursor.fetchone()
            
            if existing_doc:
                # Check if file has changed
                if existing_doc['file_hash'] != file_hash:
                    # Create new revision
                    cursor.execute(
                        "SELECT MAX(revision_number) as max_rev FROM document_revisions WHERE document_id = ?",
                        (existing_doc['id'],)
                    )
                    max_rev = cursor.fetchone()['max_rev'] or 0
                    
                    cursor.execute(
                        """INSERT INTO document_revisions 
                           (document_id, revision_number, file_path, file_hash, notes, created_at)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (existing_doc['id'], max_rev + 1, file_path, file_hash,
                         f"Auto-updated by scan. Match score: {best_score:.2f}", datetime.now())
                    )
                    
                    # Update main document record
                    cursor.execute(
                        """UPDATE documents
                           SET file_hash = ?, file_path = ?, last_scanned = ?,
                               match_confidence = ?, match_reason = ?
                           WHERE id = ?""",
                        (file_hash, file_path, datetime.now(), best_score, match_reason, existing_doc['id'])
                    )
                    documents_updated += 1
                else:
                    # File unchanged, just update last_scanned
                    cursor.execute(
                        "UPDATE documents SET last_scanned = ? WHERE id = ?",
                        (datetime.now(), existing_doc['id'])
                    )
            else:
                # New document - insert it
                doc_type = get_file_type(file_path)
                cursor.execute(
                    """INSERT INTO documents 
                       (clause_id, file_name, file_path, file_hash, document_type, 
                        status, created_at, last_scanned, match_confidence, match_reason)
                       VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?, ?)""",
                    (best_clause_id, file_name, file_path, file_hash, doc_type,
                     datetime.now(), datetime.now(), best_score, match_reason)
                )
                documents_added += 1
    
    # Update scan history
    scan_duration = (datetime.now() - start_time).total_seconds()
    cursor.execute(
        """UPDATE scan_history
           SET documents_found = ?, documents_matched = ?, documents_added = ?,
               documents_updated = ?, scan_duration = ?, completed_at = ?
           WHERE id = ?""",
        (scan_results['documents_scanned'], scan_results['documents_matched'],
         documents_added, documents_updated, scan_duration, datetime.now(), scan_id)
    )
    
    # Update monitored folders
    cursor.execute(
        """INSERT OR REPLACE INTO monitored_folders (standard_id, folder_path, last_scan)
           VALUES (?, ?, ?)""",
        (standard_id, folder_path, datetime.now())
    )
    
    conn.commit()
    conn.close()

    
# Compliance scoring
@app.get("/api/compliance-score/{standard_id}")
async def get_compliance_score(standard_id: int) -> ComplianceScore:
    """Calculate compliance score for a standard"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get all clauses with their documents
    cursor.execute("""
        SELECT c.id, c.clause_number, c.title, c.weight,
               COUNT(d.id) as doc_count
        FROM clauses c
        LEFT JOIN documents d ON c.id = d.clause_id AND d.status = 'active'
        WHERE c.standard_id = ?
        GROUP BY c.id
    """, (standard_id,))
    
    clauses = cursor.fetchall()
    conn.close()
    
    total_clauses = len(clauses)
    compliant_clauses = sum(1 for c in clauses if c['doc_count'] > 0)
    total_weight = sum(c['weight'] for c in clauses)
    weighted_score = sum(c['weight'] for c in clauses if c['doc_count'] > 0)
    
    overall_score = (weighted_score / total_weight * 100) if total_weight > 0 else 0
    
    missing_documents = [
        {
            "clause_number": c['clause_number'],
            "title": c['title'],
            "weight": c['weight']
        }
        for c in clauses if c['doc_count'] == 0
    ]
    
    # Group by element (first digit of clause number)
    element_scores = {}
    for clause in clauses:
        element = clause['clause_number'].split('.')[0]
        if element not in element_scores:
            element_scores[element] = {'total': 0, 'compliant': 0, 'weight': 0}
        element_scores[element]['total'] += 1
        element_scores[element]['weight'] += clause['weight']
        if clause['doc_count'] > 0:
            element_scores[element]['compliant'] += clause['weight']
    
    for element in element_scores:
        if element_scores[element]['weight'] > 0:
            element_scores[element]['score'] = (
                element_scores[element]['compliant'] / element_scores[element]['weight'] * 100
            )
        else:
            element_scores[element]['score'] = 0
    
    return ComplianceScore(
        standard_id=standard_id,
        overall_score=round(overall_score, 2),
        total_clauses=total_clauses,
        compliant_clauses=compliant_clauses,
        missing_documents=missing_documents,
        element_scores={k: round(v['score'], 2) for k, v in element_scores.items()}
    )

# Document management
@app.post("/api/documents/upload")
async def upload_document(clause_id: int, notes: Optional[str] = None, file: UploadFile = File(...)):
    """Upload a new document or revision"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Verify clause exists
    cursor.execute("SELECT id FROM clauses WHERE id = ?", (clause_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Clause not found")
    
    # Save file
    file_path = DOCUMENT_STORAGE / f"{clause_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    file_hash = calculate_file_hash(str(file_path))
    doc_type = get_file_type(file.filename)
    
    # Create document entry
    cursor.execute(
        """INSERT INTO documents (clause_id, file_name, file_path, file_hash, document_type)
           VALUES (?, ?, ?, ?, ?)""",
        (clause_id, file.filename, str(file_path), file_hash, doc_type)
    )
    document_id = cursor.lastrowid
    
    # Create initial revision
    cursor.execute(
        """INSERT INTO document_revisions (document_id, revision_number, file_path, file_hash, notes)
           VALUES (?, 1, ?, ?, ?)""",
        (document_id, str(file_path), file_hash, notes)
    )
    
    conn.commit()
    conn.close()
    
    return {"id": document_id, "message": "Document uploaded successfully"}

@app.get("/api/documents/{document_id}/revisions")
async def get_document_revisions(document_id: int):
    """Get all revisions for a document"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM document_revisions WHERE document_id = ? ORDER BY revision_number DESC",
        (document_id,)
    )
    revisions = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return revisions

# AI Configuration
@app.post("/api/ai-config")
async def configure_ai(config: AIConfigCreate):
    """Configure AI provider"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Deactivate all existing configs
    cursor.execute("UPDATE ai_config SET is_active = 0")
    
    # Add new config
    cursor.execute(
        """INSERT INTO ai_config (provider, api_key, model_name, is_active)
           VALUES (?, ?, ?, 1)""",
        (config.provider, config.api_key, config.model_name)
    )
    
    conn.commit()
    conn.close()
    return {"message": "AI configuration saved"}

@app.get("/api/ai-config/active")
async def get_active_ai_config():
    """Get active AI configuration"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT provider, model_name FROM ai_config WHERE is_active = 1")
    config = cursor.fetchone()
    conn.close()
    
    if not config:
        return {"provider": None, "model_name": None}
    return dict(config)

# Document reassignment
@app.post("/api/documents/{document_id}/reassign")
async def reassign_document(document_id: int, request: ReassignRequest):
    """Reassign a document to a different clause"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get current document details
        cursor.execute("SELECT id, clause_id, file_name FROM documents WHERE id = ?", (document_id,))
        document = cursor.fetchone()
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        old_clause_id = document['clause_id']
        
        if old_clause_id == request.new_clause_id:
            return {"success": True, "message": "Document already in this clause"}
        
        # Verify new clause exists
        cursor.execute("SELECT id FROM clauses WHERE id = ?", (request.new_clause_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Target clause not found")
        
        # Record the correction
        cursor.execute(
            """INSERT INTO user_corrections 
               (original_document_id, corrected_document_id, clause_id, reason, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (document_id, document_id, request.new_clause_id,
             request.reason or "Manual reassignment", datetime.now())
        )
        
        # Update the document's clause assignment
        cursor.execute(
            """UPDATE documents
               SET clause_id = ?, match_confidence = 1.0,
                   match_reason = ?
               WHERE id = ?""",
            (request.new_clause_id,
             f"Manually assigned by user: {request.reason or 'No reason provided'}",
             document_id)
        )
        
        conn.commit()
        
        # Get clause details for response
        cursor.execute(
            "SELECT clause_number, title FROM clauses WHERE id = ?",
            (request.new_clause_id,)
        )
        new_clause = cursor.fetchone()
        
        return {
            "success": True,
            "message": f"Document reassigned to {new_clause['clause_number']} - {new_clause['title']}",
            "document_id": document_id,
            "old_clause_id": old_clause_id,
            "new_clause_id": request.new_clause_id
        }
    finally:
        conn.close()

@app.get("/api/documents/unmatched")
async def get_unmatched_documents():
    """Get documents with low confidence scores"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT d.*, c.clause_number, c.title as clause_title
        FROM documents d
        JOIN clauses c ON d.clause_id = c.id
        WHERE d.match_confidence < 0.5 AND d.status = 'active'
        ORDER BY d.match_confidence ASC
        LIMIT 100
    """)
    
    documents = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return {"documents": documents, "total": len(documents)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)