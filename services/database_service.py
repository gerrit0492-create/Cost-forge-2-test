import sqlite3
from pathlib import Path

DB_PATH = Path('data/costforge.db')


def get_connection():
    return sqlite3.connect(DB_PATH)


def initialize_database():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer TEXT,
            project_name TEXT,
            sales_price REAL,
            total_cost REAL,
            margin_percent REAL
        )
    ''')

    conn.commit()
    conn.close()


def save_project(customer, project_name, sales_price, total_cost, margin_percent):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        '''
        INSERT INTO projects (
            customer,
            project_name,
            sales_price,
            total_cost,
            margin_percent
        ) VALUES (?, ?, ?, ?, ?)
        ''',
        (
            customer,
            project_name,
            sales_price,
            total_cost,
            margin_percent,
        )
    )

    conn.commit()
    conn.close()
