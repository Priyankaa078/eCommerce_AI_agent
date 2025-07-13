import streamlit as st
import sqlite3
import asyncio
from db import init_db , save_image_with_metadata , get_images_with_metadata
from llm_parser import extract_metadata_from_image
from agent_handler import ask_agent



init_db()

#page setup
st.set_page_config(page_title ="Photo Uploader", layout ="centered")

#Create two tabs
tab1 , tab2 = st.tabs(["Upload Photos" , "AI assistant"])

# upload photos
with tab1:
    st.header("Upload Handicraft Images")

    uploaded_files = st.file_uploader(
        "Choose images",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True
    )

    if uploaded_files:
        for file in uploaded_files:
            image_bytes = file.read()
            with st.spinner("Analyzing with AI..."):
                metadata = extract_metadata_from_image(image_bytes)
            save_image_with_metadata(file.name, image_bytes, metadata)
            st.success(f"{file.name} saved with metadata")

    st.subheader("Stored Handicrafts")
    images_data = get_images_with_metadata()
    if images_data:
        for name, img_blob, metadata in images_data:
            st.image(img_blob,width=100)
    else:
        st.info("No images uploaded yet.")

    # --- AI Agent Interface Below ---
    st.divider()
    st.header("Ask the AI Agent")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    user_input = st.text_input("You:", key="agent_input")

    if user_input:
        st.session_state.chat_history.append(("user", user_input))
        with st.spinner("Thinking..."):
            response = asyncio.run(ask_agent(user_input))
        st.session_state.chat_history.append(("agent", response))

    for role, message in st.session_state.chat_history:
        st.markdown(f"**{role.capitalize()}:** {message}")


   
#Placeholder
with tab2:
    st.title("🧵 Chat with Sales Agent")

    # customer_name = st.text_input("Enter your name to begin:", key="chat_name")

    # if customer_name:
    #     table_name = sanitize_name(customer_name)

    #     def get_chat_history():
    #         conn = sqlite3.connect("chat_history.db")
    #         conn.execute(f'''
    #             CREATE TABLE IF NOT EXISTS {table_name} (
    #                 id INTEGER PRIMARY KEY AUTOINCREMENT,
    #                 sender TEXT,
    #                 message TEXT
    #             )
    #         ''')
    #         cur = conn.execute(f"SELECT sender, message FROM {table_name}")
    #         rows = cur.fetchall()
    #         conn.close()
    #         return rows

    #     chat_history = get_chat_history()

    #     st.markdown("---")
    #     st.subheader("💬 Conversation")

    #     for sender, message in chat_history:
    #         with st.chat_message("user" if sender == "user" else "assistant"):
    #             st.markdown(message)

    #     user_input = st.chat_input("Type your message...")
    #     if user_input:
    #         with st.chat_message("user"):
    #             st.markdown(user_input)

    #         agent_reply = handle_user_message(customer_name, user_input)

    #         with st.chat_message("assistant"):
    #             st.markdown(agent_reply)