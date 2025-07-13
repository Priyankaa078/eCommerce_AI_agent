import os
from openai import OpenAI
import asyncio
from agents import Agent, Runner, function_tool
from dotenv import load_dotenv
import sqlite3
import json
from PIL import Image
import io
import requests
from bs4 import BeautifulSoup

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


@function_tool
def search_client():
    """
    Uses the crafts database to extract trigger keywords (from metadata and images),
    searches for potential clients from the client database using those triggers,
    and stores matching clients in potential_clients.db.
    Missing fields like email are filled as 'NA'. Reason explains why the client matched.
    """
    try:
        # --- Load triggers from crafts metadata and images ---
        print("Connecting to images.db...")
        conn_crafts = sqlite3.connect("images.db", check_same_thread=False)
        cursor_crafts = conn_crafts.cursor()
        cursor_crafts.execute("SELECT metadata, image FROM images")
        rows = cursor_crafts.fetchall()
        conn_crafts.close()
        print(f"Loaded {len(rows)} image rows.")

        triggers = set()

        for metadata_str, image_blob in rows:
            try:
                metadata = json.loads(metadata_str)
            except json.JSONDecodeError:
                print("Invalid JSON in metadata.")
                continue

            for key in ['type', 'style', 'color', 'material', 'estimated_size', 'handcrafted']:
                value = metadata.get(key)
                if value:
                    if isinstance(value, list):
                        triggers.update(value)
                    else:
                        triggers.add(str(value))

            if image_blob:
                try:
                    image = Image.open(io.BytesIO(image_blob)).convert("RGB")
                    colors = image.getcolors(maxcolors=1000000)
                    if colors:
                        dominant_color = max(colors, key=lambda item: item[0])[1]
                        color_str = f"rgb{dominant_color}"
                        triggers.add(color_str)
                except Exception as img_err:
                    print(f"Image error: {img_err}")
                    continue

        print("Extracted triggers:", triggers)

        # --- Load client database ---
        print("Connecting to meesho.db...")
        conn_clients = sqlite3.connect("meesho.db", check_same_thread=False)
        cursor_clients = conn_clients.cursor()
        cursor_clients.execute("SELECT id, name, address, last_bought_item, liked_products, email, phone FROM customers")
        all_clients = cursor_clients.fetchall()
        conn_clients.close()
        print(f"Loaded {len(all_clients)} clients.")

        matched_clients = []

        for row in all_clients:
            id_, name, address, last_bought, liked, email, phone = row
            text_blob = f"{(last_bought or '')} {(liked or '')} {(address or '')}".lower()
            matched_triggers = [t for t in triggers if t.lower() in text_blob]
            if matched_triggers:
                reason = f"Matches craft triggers: {', '.join(matched_triggers)}"
                matched_clients.append((name, email if email else "NA", reason))

        print(f"{len(matched_clients)} clients matched.")

        # --- Save to potential_clients.db ---
        print("Saving to potential_clients.db...")
        conn_out = sqlite3.connect("potential_clients.db", check_same_thread=False)
        cursor_out = conn_out.cursor()
        cursor_out.execute("""
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                email TEXT,
                reason TEXT
            )
        """)
        if matched_clients:
            cursor_out.executemany("INSERT INTO clients (name, email, reason) VALUES (?, ?, ?)", matched_clients)
            conn_out.commit()
        conn_out.close()
        print("Data saved successfully.")

        if not matched_clients:
            return "No potential clients matched current craft triggers."

        return [f"{name} ({email}) - {reason}" for name, email, reason in matched_clients]

    except Exception as e:
        return f"Error accessing databases: {e}\nTrace:\n{traceback.format_exc()}"


@function_tool
def message_framer(name: str, followup_query: str = "") -> str:
    """
    Frames a personalized pitch message for the client (first message),
    or responds to a follow-up query using client and craft data.
    The most relevant craft is selected based on client's interest (reason).
    """
    # Load client info
    try:
        conn_client = sqlite3.connect("potential_clients.db")
        cursor_client = conn_client.cursor()
        cursor_client.execute("SELECT email, reason FROM clients WHERE customer_name = ?", (name,))
        result = cursor_client.fetchone()
        conn_client.close()
        if not result:
            return f"No data found for {name} in potential clients database."
        email, reason = result
    except:
        return f"Failed to fetch client data for {name}."

    # Load crafts info
    try:
        conn_craft = sqlite3.connect("crafts.db")
        cursor_craft = conn_craft.cursor()
        cursor_craft.execute("SELECT name, metadata FROM crafts")
        crafts = cursor_craft.fetchall()
        conn_craft.close()
    except:
        return f"Failed to load crafts info."

    if not crafts:
        return f"No crafts found to reference."

    # Match most relevant craft based on reason
    reason_lower = reason.lower()
    best_match = None
    best_score = 0

    for craft_name, metadata_json in crafts:
        metadata = json.loads(metadata_json)
        fields = [
            str(metadata.get("type", "")),
            str(metadata.get("style", "")),
            str(metadata.get("color", "")),
            str(metadata.get("material", "")),
            str(metadata.get("estimated_size", "")),
            str(metadata.get("handcrafted", ""))
        ]
        match_score = sum(1 for field in fields if field.lower() in reason_lower)
        if match_score > best_score:
            best_score = match_score
            best_match = (craft_name, metadata)

    if not best_match:
        craft_name, metadata = crafts[0]  # fallback to first craft
    else:
        craft_name, metadata = best_match

    style = metadata.get("style", "unique")
    material = metadata.get("material", "premium material")
    estimated_size = metadata.get("estimated_size", "standard size")
    handcrafted = metadata.get("handcrafted", "yes")
    color = metadata.get("color", "classic tone")

    #  Message logic
    if not followup_query.strip():
        # Initial pitch
        message = (
            f"Hi {name},\n\n"
            f"We noticed your interest: {reason}.\n"
            f"Based on that, we thought you'd love our handcrafted {craft_name}, made from {material}, "
            f"featuring a {style} style in {color}. It's approximately {estimated_size} and handcrafted: {handcrafted}.\n\n"
            f"Would you like a special offer or more details?\n\n"
            f"Warm regards,\nThe Craft Team"
        )
    else:
        # Follow-up query handling
        query = followup_query.lower()
        response_lines = [f"Hi {name}, thanks for following up!"]

        if "price" in query or "cost" in query:
            response_lines.append(f"The {craft_name} is affordably priced. Let us know your budget for a custom quote.")
        elif "size" in query:
            response_lines.append(f"The {craft_name} is approximately {estimated_size}.")
        elif "material" in query:
            response_lines.append(f"It is made from high-quality {material}.")
        elif "handmade" in query or "handcrafted" in query:
            response_lines.append(f"Yes, this product is handcrafted: {handcrafted}.")
        elif "color" in query:
            response_lines.append(f"It comes in a beautiful {color} tone.")
        else:
            response_lines.append("Let us know your query and we’ll provide full details!")

        message = "\n".join(response_lines)

    return message


@function_tool
def sender_and_receiver(name: str, agent_message: str) -> str:
    """
    Takes the agent's message and the client's name.
    Simulates sending the message to the user and capturing their query.
    Stores the agent message and user query in a table named after the user in chat_history.db.
    """
    # Show agent message to user (simulate chatbot interaction)
    print(f"\n📩 Agent to {name}:\n{agent_message}\n")

    # Simulate user input (replace with actual chatbot integration later)
    user_query = input(f"💬 {name}'s reply: ").strip()

    conn = sqlite3.connect("chat_history.db")
    cursor = conn.cursor()

    table_name = f"chat_{name.lower().replace(' ', '_')}"

    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_message TEXT,
            user_query TEXT
        )
    """)

    cursor.execute(f"""
        INSERT INTO {table_name} (agent_message, user_query)
        VALUES (?, ?)
    """, (agent_message, user_query))

    conn.commit()
    conn.close()

    return user_query


agent = Agent(
    name="CraftSalesAssistant",
    instructions="""
You are CraftSalesAssistant — a smart and proactive AI agent designed to help discover potential buyers for handmade crafts, 
send personalized pitch messages, and handle interactive follow-up queries. You operate using three specialized tools:

---

Available Tools:

1. search_client  
   - Extracts trigger keywords (style, type, color, material, etc.) from `crafts.db`, using metadata and image content.  
   - Searches for matching potential clients from `clients.db` and a web search.  
   - Stores matched clients into `potential_clients.db` with a clear reason why they matched.  
   - If you are ever told to “fill clients database”, “find potential clients”, or anything similar, you must invoke this tool.

2. message_framer  
   - Takes the client’s name and an optional follow-up query.  
   - For initial contact: it fetches their interest from `potential_clients.db` and matches them with the most relevant craft from `crafts.db`.  
   - For follow-ups: it generates a helpful and relevant response using the associated craft metadata (e.g., color, material, handcrafted, size).  
   - Your replies should only come from this tool — do not hardcode messages.

3. sender_and_receiver  
   - Takes the client’s name and the message generated by `message_framer`.  
   - Simulates delivering the message to the user (via chatbot).  
   - Receives a follow-up query from the user.  
   - Logs both the agent message and user query in a `chat_history.db` table named after the client.  
   - Returns the user’s follow-up query.  
   - After receiving a user query from this tool, you must send it back to `message_framer` (with name and query) to generate the reply.

---

Agent Responsibilities:

- Understand when to use each tool — do not respond directly yourself.
- Use `search_client` first if the database of potential clients needs to be filled or refreshed.
- Use `message_framer` to pitch or respond to a client's query (based on name and reason).
- Use `sender_and_receiver` to pass messages to the chatbot/user, then wait for their response.
- After receiving the user's query, immediately pass it again (with name) to `message_framer` for a reply.
- Always maintain a friendly, clear, and helpful tone based on product knowledge — never guess outside the database.
- After completing any user instruction (like filling the clients database, sending a message, or replying to a query), always output a confirmation message indicating that the task has been completed successfully.

Your goal is to automate the craft pitching pipeline:  
Find clients → Pitch personalized message → Handle responses → Log all chat history.
""",
    tools=[search_client, message_framer, sender_and_receiver],
    model="gpt-4o"
)


# Interface to ask the agent
async def ask_agent(prompt: str) -> str:
   result = await Runner.run(agent , prompt)
   return result.final_output.strip() if result.final_output else "No response generated."