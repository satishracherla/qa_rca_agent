import sqlite3
from datetime import datetime
from typing import List, Dict, Optional, Any

DATABASE = 'qa_agent.db'

def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Ensure a fresh schema for tests by dropping the issues table if it exists
    cursor.execute('DROP TABLE IF EXISTS issues')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS issues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            severity TEXT,
            status TEXT DEFAULT 'open',
            category TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS root_causes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_id INTEGER,
            cause TEXT NOT NULL,
            category TEXT,
            evidence TEXT,
            confidence REAL DEFAULT 0.0,
            FOREIGN KEY (issue_id) REFERENCES issues (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS five_whys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_id INTEGER,
            level INTEGER,
            question TEXT NOT NULL,
            answer TEXT,
            FOREIGN KEY (issue_id) REFERENCES issues (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fishbone_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_id INTEGER,
            category TEXT NOT NULL,
            items TEXT,
            FOREIGN KEY (issue_id) REFERENCES issues (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_id INTEGER,
            recommendation TEXT NOT NULL,
            priority TEXT,
            status TEXT DEFAULT 'pending',
            FOREIGN KEY (issue_id) REFERENCES issues (id)
        )
    ''')
    
    conn.commit()
    conn.close()

class Issue:
    def __init__(self, title: str, description: str = "", severity: str = "medium", 
                 category: str = "", id: int = None, status: str = "open"):
        self.id = id
        self.title = title
        self.description = description
        self.severity = severity
        self.category = category
        self.status = status
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.root_causes: List['RootCause'] = []
        self.recommendations: List['Recommendation'] = []
    
    def save(self):
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        if self.id:
            cursor.execute('''
                UPDATE issues SET title=?, description=?, severity=?, status=?, 
                category=?, updated_at=? WHERE id=?
            ''', (self.title, self.description, self.severity, self.status, 
                  self.category, datetime.now(), self.id))
        else:
            cursor.execute('''
                INSERT INTO issues (title, description, severity, status, category)
                VALUES (?, ?, ?, ?, ?)
            ''', (self.title, self.description, self.severity, self.status, 
                  self.category))
            self.id = cursor.lastrowid
        
        conn.commit()
        conn.close()
    
    @staticmethod
    def get_all() -> List['Issue']:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM issues ORDER BY created_at DESC')
        rows = cursor.fetchall()
        conn.close()
        
        issues = []
        for row in rows:
            issue = Issue(
                id=row[0], title=row[1], description=row[2],
                severity=row[3], status=row[4], category=row[5]
            )
            issues.append(issue)
        return issues
    
    @staticmethod
    def get_by_id(issue_id: int) -> Optional['Issue']:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM issues WHERE id=?', (issue_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return Issue(
                id=row[0], title=row[1], description=row[2],
                severity=row[3], status=row[4], category=row[5]
            )
        return None

class RootCause:
    def __init__(self, issue_id: int, cause: str, category: str = "",
                 evidence: str = "", confidence: float = 0.0, id: int = None):
        self.id = id
        self.issue_id = issue_id
        self.cause = cause
        self.category = category
        self.evidence = evidence
        self.confidence = confidence
    
    def save(self):
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        if self.id:
            cursor.execute('''
                UPDATE root_causes SET cause=?, category=?, evidence=?, confidence=?
                WHERE id=?
            ''', (self.cause, self.category, self.evidence, self.confidence, self.id))
        else:
            cursor.execute('''
                INSERT INTO root_causes (issue_id, cause, category, evidence, confidence)
                VALUES (?, ?, ?, ?, ?)
            ''', (self.issue_id, self.cause, self.category, self.evidence, self.confidence))
            self.id = cursor.lastrowid
        
        conn.commit()
        conn.close()
    
    @staticmethod
    def get_by_issue(issue_id: int) -> List['RootCause']:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM root_causes WHERE issue_id=?', (issue_id,))
        rows = cursor.fetchall()
        conn.close()
        
        return [RootCause(
            id=row[0], issue_id=row[1], cause=row[2],
            category=row[3], evidence=row[4], confidence=row[5]
        ) for row in rows]

class FiveWhys:
    def __init__(self, issue_id: int, level: int, question: str, 
                 answer: str = "", id: int = None):
        self.id = id
        self.issue_id = issue_id
        self.level = level
        self.question = question
        self.answer = answer
    
    def save(self):
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        if self.id:
            cursor.execute('''
                UPDATE five_whys SET question=?, answer=? WHERE id=?
            ''', (self.question, self.answer, self.id))
        else:
            cursor.execute('''
                INSERT INTO five_whys (issue_id, level, question, answer)
                VALUES (?, ?, ?, ?)
            ''', (self.issue_id, self.level, self.question, self.answer))
            self.id = cursor.lastrowid
        
        conn.commit()
        conn.close()
    
    @staticmethod
    def get_by_issue(issue_id: int) -> List['FiveWhys']:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM five_whys WHERE issue_id=? ORDER BY level', (issue_id,))
        rows = cursor.fetchall()
        conn.close()
        
        return [FiveWhys(
            id=row[0], issue_id=row[1], level=row[2],
            question=row[3], answer=row[4]
        ) for row in rows]

class FishboneCategory:
    def __init__(self, issue_id: int, category: str, items: str = "", id: int = None):
        self.id = id
        self.issue_id = issue_id
        self.category = category
        self.items = items
    
    def save(self):
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        if self.id:
            cursor.execute('''
                UPDATE fishbone_categories SET category=?, items=? WHERE id=?
            ''', (self.category, self.items, self.id))
        else:
            cursor.execute('''
                INSERT INTO fishbone_categories (issue_id, category, items)
                VALUES (?, ?, ?)
            ''', (self.issue_id, self.category, self.items))
            self.id = cursor.lastrowid
        
        conn.commit()
        conn.close()
    
    @staticmethod
    def get_by_issue(issue_id: int) -> List['FishboneCategory']:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM fishbone_categories WHERE issue_id=?', (issue_id,))
        rows = cursor.fetchall()
        conn.close()
        
        return [FishboneCategory(
            id=row[0], issue_id=row[1], category=row[2], items=row[3]
        ) for row in rows]

class Recommendation:
    def __init__(self, issue_id: int, recommendation: str, priority: str = "medium",
                 status: str = "pending", id: int = None):
        self.id = id
        self.issue_id = issue_id
        self.recommendation = recommendation
        self.priority = priority
        self.status = status
    
    def save(self):
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        if self.id:
            cursor.execute('''
                UPDATE recommendations SET recommendation=?, priority=?, status=? WHERE id=?
            ''', (self.recommendation, self.priority, self.status, self.id))
        else:
            cursor.execute('''
                INSERT INTO recommendations (issue_id, recommendation, priority, status)
                VALUES (?, ?, ?, ?)
            ''', (self.issue_id, self.recommendation, self.priority, self.status))
            self.id = cursor.lastrowid
        
        conn.commit()
        conn.close()
    
    @staticmethod
    def get_by_issue(issue_id: int) -> List['Recommendation']:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM recommendations WHERE issue_id=?', (issue_id,))
        rows = cursor.fetchall()
        conn.close()
        
        return [Recommendation(
            id=row[0], issue_id=row[1], recommendation=row[2],
            priority=row[3], status=row[4]
        ) for row in rows]
