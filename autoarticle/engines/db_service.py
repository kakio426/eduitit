
import sqlite3
import json
import os
import uuid
from engines.constants import DB_PATH

class DatabaseService:
    def __init__(self, db_path=None):
        self.db_path = db_path if db_path else DB_PATH
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS articles (
                id TEXT PRIMARY KEY,
                date TEXT,
                school TEXT,
                grade TEXT,
                event_name TEXT,
                location TEXT,
                tone TEXT,
                keywords TEXT,
                title TEXT,
                content TEXT,
                images TEXT,
                hashtags TEXT
            )
        ''')
        conn.commit()
        conn.close()

    def save_article(self, data):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO articles (id, date, school, grade, event_name, location, tone, keywords, title, content, images, hashtags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('id', str(uuid.uuid4())),
            str(data['date']),
            data['school'],
            data['grade'],
            data['event_name'],
            data['location'],
            data['tone'],
            data['keywords'],
            data['title'],
            data['content'],
            data['images'],
            data['hashtags']
        ))
        conn.commit()
        conn.close()

    def get_all_articles(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM articles ORDER BY date ASC')
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def update_article(self, article_id, title, content):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('UPDATE articles SET title = ?, content = ? WHERE id = ?', (title, content, article_id))
        conn.commit()
        conn.close()
        return cursor.rowcount > 0

    def migrate_from_csv(self, csv_path):
        if not os.path.exists(csv_path):
            return
        import pandas as pd
        df = pd.read_csv(csv_path, encoding='utf-8-sig')
        for _, row in df.iterrows():
            try:
                self.save_article(row.to_dict())
            except sqlite3.IntegrityError:
                pass # Already exists
