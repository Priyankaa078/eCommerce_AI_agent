import streamlit as st
import sqlite3
import asyncio

def fetch_clients():
    conn = sqlite3.connect("potential_clients.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name, email, reason FROM clients")
    clients = cursor.fetchall()
    conn.close()
    return clients

def fetch_messaged_clients():
    conn = sqlite3.connect("potential_clients.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messaged_clients (
            name TEXT PRIMARY KEY
        )
    """)
    cursor.execute("SELECT name FROM messaged_clients")
    rows = cursor.fetchall()
    conn.close()
    return {name for (name,) in rows}

def mark_client_messaged(name):
    conn = sqlite3.connect("potential_clients.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO messaged_clients (name) VALUES (?)", (name,))
    conn.commit()
    conn.close()

def fetch_chat_history(name):
    table_name = f"chat_{name.lower().replace(' ', '_')}"
    
    conn = sqlite3.connect("chat_history.db")
    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT sender, message FROM {table_name}")
        chats = cursor.fetchall()
    except Exception:
        chats = []
    conn.close()
    return chats

def chat_history_user():
    table_name = "chat_hardik_sharma"
    conn = sqlite3.connect("chat_history.db")
    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT id, sender, message FROM {table_name} ORDER BY id")
        chats = cursor.fetchall()
    except Exception:
        chats = []
    conn.close()
    return chats

def reset_chat_history_preserve_first():
    table_name = "chat_hardik_sharma"
    conn = sqlite3.connect("chat_history.db")
    cursor = conn.cursor()
    cursor.execute(f"DELETE FROM {table_name} WHERE id != 1")
    conn.commit()
    conn.close()