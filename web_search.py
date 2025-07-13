import sqlite3
import json
import os
from openai import OpenAI
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import time

#load API key
load_dotenv()
client = OpenAI(api_key = os.getenv("OPENAI_API_KEY"))

#connect to database
conn = sqlite3.connect("images.db")
cursor = conn.cursor()

#get all rows with valid metadata
cursor.execute("SELECT id, metadata FROM images")
rows = cursor.fetchall()

headers ={
    "User-Agent":"Mozilla/5.0"
}

def generate_query(metadata:dict)->str:
    prompt = f"""You are helping monitor the internet for people who might be interested in handcrafted items.

Given the following metadata:
{json.dumps(metadata, indent=2)}

Generate a detailed, natural-sounding Google search query that a person might type when they are interested in or curious about this kind of item — especially focusing on the "type" field. 

Do NOT write like an advertisement. 
Include terms that signal intent, interest, or curiosity (e.g. ideas, designs, inspiration, handmade, how to make, where to find, etc.).

Output only the search query string."""
    
    response = client.chat.completions.create(
        model ="gpt-4o",
        messages = [{"role":"user","content":prompt}],
        temperature =0.7
    )

    return response.choices[0].message.content.strip()


def google_search(query:str):
    url = f"https://www.google.com/search?q={requests.utils.quote(query)}"
    resp = requests.get(url , headers=headers)
    soup = BeautifulSoup(resp.text,"html.parser")

    results =[]
    for g in soup.select("div.g"):
        a = g.find("a")
        if not a or not a.get("href"):
            continue
        title = a.get_text(strip=True)
        link = a["href"]
        snippet = g.find("span")
        results.append({
            "title":title,
            "link":link,
            "snippet":snippet.get_text(strip=True) if snippet else " "

        })

    return results[:5]

def perform_search(query: str):
    print(f"  🔍 Searching on Bing...")
    url = f"https://www.bing.com/search?q={requests.utils.quote(query)}"
    resp = requests.get(url, headers=headers)

    soup = BeautifulSoup(resp.text, "html.parser")
    results = []

    for li in soup.select("li.b_algo"):
        title_tag = li.select_one("h2")
        link_tag = title_tag.find("a") if title_tag else None
        snippet_tag = li.select_one("p")

        if not (title_tag and link_tag):
            continue

        title = title_tag.get_text(strip=True)
        link = link_tag["href"]
        snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""

        results.append({
            "title": title,
            "link": link,
            "snippet": snippet
        })

    print(f"  ↳ Got {len(results)} results from Bing")
    return results[:5]


#process each item
output =[]

for row in rows :
    row_id ,metadata_raw = row
    try:
        metadata = json.loads(metadata_raw)
        query = generate_query(metadata)
        print (f"[ID{row_id}] Query-> {query}")
        time.sleep(2) #avoid google block

        results = perform_search(query)

        print(f"  ↳ Got {len(results)} results from Google")
        if len(results) == 0:
             print("  ⚠️ No results returned. Skipping this item.")


        for r in results:
            matched = [k for k in metadata if isinstance(metadata[k],str) and metadata[k].lower() in r["snippet"].lower()]
            output.append({
                "item_id" : row_id,
                "query":query,
                "title":r["title"],
                "link":r["link"],
                "snippet":r["snippet"],
                "matched_keywords":matched
            })
    except Exception as e:
        print(f"error in row{row_id}:{e}")

# Create table for storing search leads
cursor.execute("""
CREATE TABLE IF NOT EXISTS search_leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER,
    query TEXT,
    title TEXT,
    link TEXT,
    snippet TEXT,
    matched_keywords TEXT
)
""")

# Insert each result into the table
for entry in output:
    cursor.execute("""
        INSERT INTO search_leads (item_id, query, title, link, snippet, matched_keywords)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        entry["item_id"],
        entry["query"],
        entry["title"],
        entry["link"],
        entry["snippet"],
        ", ".join(entry["matched_keywords"])
    ))

# Commit and close
conn.commit()
conn.close()

print("Output saved to search_leads table in images.db")

