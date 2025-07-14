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
import re

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
                # Use LLM to generate reason summary
                reason_prompt = f"""
                You are an expert product marketer.

                Craft Product Triggers: {', '.join(matched_triggers)}
                Client Details:
                    - Name: {name}
                    - Last Bought: {last_bought}
                    - Liked Products: {liked}
                    - Address: {address}

                Write a short professional summary explaining why this client is a good match for the crafts.
                """

                reason = client.chat.completions.create(
                    model="gpt-4o",  
                    messages=[{"role": "user", "content": reason_prompt}]
                ).choices[0].message.content.strip()

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
    Frames a personalized pitch message or follow-up reply using client and craft info.
    Uses LLM to generate messages.
    Also stores follow-up queries in chat_history.db as user messages.
    """

    # Fetch client details
    try:
        conn_client = sqlite3.connect("potential_clients.db")
        cursor_client = conn_client.cursor()
        cursor_client.execute("SELECT email, reason FROM clients WHERE name = ?", (name,))
        result = cursor_client.fetchone()
        conn_client.close()
        if not result:
            return f"No data found for {name} in potential clients database."
        email, reason = result
    except Exception as e:
        return f"Failed to fetch client data for {name}: {e}"

    # Fetch crafts info (images + metadata)
    try:
        conn_craft = sqlite3.connect("images.db")
        cursor_craft = conn_craft.cursor()
        cursor_craft.execute("SELECT image, metadata FROM images")
        crafts = cursor_craft.fetchall()
        conn_craft.close()
    except Exception as e:
        return f"Failed to load crafts info: {e}"

    if not crafts:
        return f"No crafts found to reference."

    # Match most relevant craft based on reason
    reason_lower = reason.lower()
    best_match = None
    best_score = 0

    for image_blob, metadata_json in crafts:
        # Safe JSON parsing with error handling
        try:
            if metadata_json is None or metadata_json == "":
                metadata = {}
            else:
                metadata = json.loads(metadata_json)
                
            # Ensure metadata is a dictionary
            if not isinstance(metadata, dict):
                metadata = {}
                
        except (json.JSONDecodeError, TypeError) as e:
            # If JSON parsing fails, create empty dict
            metadata = {}
        
        # Extract fields safely with default values
        fields = [
            str(metadata.get("type", "")),
            str(metadata.get("style", "")),
            str(metadata.get("color", "")),
            str(metadata.get("material", "")),
            str(metadata.get("estimated_size", "")),
            str(metadata.get("handcrafted", ""))
        ]
        
        # Calculate match score
        match_score = sum(1 for field in fields if field.lower() and field.lower() in reason_lower)
        if match_score > best_score:
            best_score = match_score
            best_match = (image_blob, metadata)

    # Use best match or fallback to first craft
    if not best_match:
        try:
            image_blob, metadata_json = crafts[0]
            # Apply same safe parsing for fallback
            if metadata_json is None or metadata_json == "":
                metadata = {}
            else:
                metadata = json.loads(metadata_json)
                if not isinstance(metadata, dict):
                    metadata = {}
        except (json.JSONDecodeError, TypeError):
            metadata = {}
        best_match = (image_blob, metadata)
    
    image_blob, metadata = best_match

    # Extract product details with safe defaults
    style = metadata.get("style", "unique")
    material = metadata.get("material", "premium material")
    estimated_size = metadata.get("estimated_size", "standard size")
    handcrafted = metadata.get("handcrafted", "yes")
    color = metadata.get("color", "classic tone")

    # LLM-based message framing
    product_details = f"""
    Client Name: {name}
    Product Details:
        - Material: {material}
        - Style: {style}
        - Color: {color}
        - Size: {estimated_size}
        - Handcrafted: {handcrafted}
    Reason for Interest: {reason}
    """

    if not followup_query.strip():
        # --- Generate First Pitch Message ---
        prompt = f"""
        You are a creative marketing assistant.

        Using the following client and product details, write a short(2-3 lines), friendly, and attractive message that encourages the client to explore the product:

        {product_details}

        Keep it professional yet warm.
        After warm ragards add from crafts team only.
        """
    else:
        # --- Store follow-up query in chat_history.db ---
        try:
            table_name = f"chat_{name.lower().replace(' ', '_')}"

            conn_chat = sqlite3.connect("chat_history.db")
            cursor_chat = conn_chat.cursor()

            cursor_chat.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender TEXT,
                    message TEXT
                )
            """)
            cursor_chat.execute(f"INSERT INTO {table_name} (sender, message) VALUES (?, ?)", ('user', followup_query))
            conn_chat.commit()
            conn_chat.close()
        except Exception as e:
            return f"Failed to store query in chat_history.db: {e}"

        # --- Generate Follow-up Reply ---
        prompt = f"""
        You are a helpful product assistant.

        A client named {name} has asked the following question: "{followup_query}"

        Product Details:
            - Material: {material}
            - Style: {style}
            - Color: {color}
            - Size: {estimated_size}
            - Handcrafted: {handcrafted}

        Write a short(2-3 lines), polite, and informative reply answering their query.
        """

    # Generate message using LLM
    try:
        message = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}]
        ).choices[0].message.content.strip()
        
        return message
    except Exception as e:
        return f"Failed to generate message: {e}"

@function_tool
def sender_tool(name: str, message: str) -> str:
    """
    Receives a message from the agent, stores it in the chat log,
    and simulates sending it to the user.

    - Stores sender='agent', message=agent_message.
    - Simulates sending to user.
    """

    if not message:
        return "No agent message provided."

    table_name = f"chat_{name.lower().replace(' ', '_')}"

    conn = sqlite3.connect("chat_history.db")
    cursor = conn.cursor()

    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT,
            message TEXT
        )
    """)

    # Store agent message
    cursor.execute(f"""
        INSERT INTO {table_name} (sender, message)
        VALUES (?, ?)
    """, ("agent", message))

    conn.commit()
    conn.close()

    # Simulate sending (optional)
    print(f"\nAgent to {name}: {message}\n")

    return "Agent message sent to user and stored."


agent = Agent(
    name="CraftSalesAssistant",
    instructions="""
You are CraftSalesAssistant — a smart and proactive AI agent designed to help discover potential buyers for handmade crafts, 
send personalized pitch messages, and handle interactive follow-up queries. You operate using three specialized tools:

Agent Responsibilities:

- Understand when to use each tool — do not directly respond by yourself.
- Use search_client tool if user asks you to fill or refersh the database of potential clients.
-if a you to are asked to send a message to clients follow these two steps -
    1. Use message_framer tool to frame the message . The followup_query parameter is null in this case .
    2. Use sender_tool to send a message. ALWAYS use the message returned from message_framer tool as the message parameter in sender_tool
-if you receive a query like some user replied as something follow these steps -
    1. Use message_framer tool to frame the message . The followup_query parameter is the reply .
    2. Use sender_tool to send a message. ALWAYS use the message returned from message_framer tool as the message parameter in sender_tool

- Always maintain a friendly, clear, and helpful tone based on product knowledge — never guess outside the database.
- After completing any instruction ,always output a confirmation message indicating that the task has been completed successfully.


""",
    tools=[search_client, message_framer, sender_tool],
    model="gpt-4o"
)


# Interface to ask the agent
async def ask_agent(prompt: str) -> str:
   result = await Runner.run(agent , prompt)
   return result.final_output.strip() if result.final_output else "No response generated."


