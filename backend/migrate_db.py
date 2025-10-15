"""
Database migration script - adds new columns for enhanced matching
"""
import sqlite3

DB_PATH = "compliance.db"

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("Starting database migration...")
    
    # Add match_confidence to documents table
    try:
        cursor.execute("ALTER TABLE documents ADD COLUMN match_confidence REAL DEFAULT 0.0")
        print("✓ Added match_confidence column to documents")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            print("✓ match_confidence column already exists")
        else:
            raise
    
    # Add match_reason to documents table
    try:
        cursor.execute("ALTER TABLE documents ADD COLUMN match_reason TEXT")
        print("✓ Added match_reason column to documents")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            print("✓ match_reason column already exists")
        else:
            raise
    
    # Add new columns to scan_history
    try:
        cursor.execute("ALTER TABLE scan_history ADD COLUMN documents_matched INTEGER DEFAULT 0")
        cursor.execute("ALTER TABLE scan_history ADD COLUMN documents_added INTEGER DEFAULT 0")
        cursor.execute("ALTER TABLE scan_history ADD COLUMN documents_updated INTEGER DEFAULT 0")
        print("✓ Added statistics columns to scan_history")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            print("✓ scan_history columns already exist")
        else:
            raise
    
    conn.commit()
    conn.close()
    
    print("\n✓ Migration completed successfully!")

if __name__ == "__main__":
    migrate()