import sqlite3
import json

#initialize db and create table if it doesn,t exist
def init_db():
    conn = sqlite3.connect("images.db")
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS images(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            image BLOB,
            metadata TEXT
        )
    ''')
    conn.commit()
    conn.close()

#save image to db
def save_image_with_metadata(name , image_bytes , metadata_dict):
    conn = sqlite3.connect("images.db")
    c = conn.cursor()
    c.execute("INSERT INTO images (name , image , metadata) VALUES(?,? ,?)" ,(name ,image_bytes , json.dumps(metadata_dict)))
    conn.commit()
    conn.close()

#get all saved images():
def get_images_with_metadata():
    conn = sqlite3.connect("images.db")
    c = conn.cursor()
    c.execute("SELECT name, image, metadata FROM images")
    rows = c.fetchall()
    conn.close()
    return [(name , img_blob , json.loads(metadata)) for name, img_blob , metadata in rows]