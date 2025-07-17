import os
import streamlit as st
from dotenv import load_dotenv

ENV_FILE = '.env'
load_dotenv(ENV_FILE)

import sqlite3
import asyncio
import openai
from db import init_db, save_image_with_metadata, get_images_with_metadata
from function_handler import fetch_chat_history, fetch_clients, fetch_messaged_clients, mark_client_messaged, chat_history_user, reset_chat_history_preserve_first , load_api_key_from_env ,save_api_key_to_env

api_key = load_api_key_from_env()

if not api_key:
    st.warning("OpenAI API key not found. Please enter it below:")
    
    user_api_key = st.text_input("Enter your OpenAI API Key", type="password", key="api_key_input")
    
    if user_api_key:
        save_api_key_to_env(user_api_key)
        st.success("API key saved! Please refresh the page.")
        st.stop()
    
    st.stop()

try:
    from llm_parser import extract_metadata_from_image
    from agent_handler import ask_agent_streaming 
except Exception as e:
    st.error(f"Error importing modules: {str(e)}")
    st.error("Please refresh the page after setting your API key.")
    st.stop()

async def stream_agent(user_query, status_placeholder=None):
    final_response = ""

    async for event in ask_agent_streaming(user_query):
        if hasattr(event, 'type') and event.type == "run_item_stream_event":
            if hasattr(event, 'item') and hasattr(event.item, 'type') and event.item.type == "tool_call_item":
                tool_name = event.item.raw_item.name.replace("_", " ").title()
                if status_placeholder:
                    status_placeholder.markdown(
                        f"🔧 <b>Calling tool:</b> {tool_name}",
                        unsafe_allow_html=True
                    )

        elif hasattr(event, 'type') and event.type == "final_response":
            final_response = getattr(event, 'content', "")

    return final_response



def safe_async_run(coro):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    if loop.is_running():
        return asyncio.ensure_future(coro)
    else:
        return loop.run_until_complete(coro)


init_db()

st.set_page_config(page_title="Sales Agent", layout="centered")
tab1, tab2 = st.tabs(["Craftsman interface", "Dummy user interface"])

# ---------------------- Tab 1: Craftsman Interface ----------------------
with tab1:
    st.header("Upload Handicraft Images")

    uploaded_files = st.file_uploader("Choose images", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

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
            st.image(img_blob, width=100)
    else:
        st.info("No images uploaded yet.")

    # ---------- Divider: Potential Clients Section ----------
    st.divider()
    st.header("Potential Clients")

    clients = fetch_clients()
    messaged_clients = fetch_messaged_clients()
    selected_users = []

    if "open_chat" not in st.session_state:
        st.session_state["open_chat"] = None

    if clients:
        st.write("Select clients to message:")

        for idx, (name, email, reason) in enumerate(clients):
            col1, col2 = st.columns([4, 1])

            with col1:
                if name in messaged_clients:
                    st.checkbox(f"{name} ({email})", key=f"user_{idx}", value=True, disabled=True)
                else:
                    checked = st.checkbox(f"{name} ({email})", key=f"user_{idx}")
                    if checked:
                        selected_users.append(name)

            with col2:
                if st.button("View Chat", key=f"chat_{idx}"):
                    st.session_state["open_chat"] = name

        if selected_users:
            st.success(f"Selected Clients: {selected_users}")

        if st.button("Send Message to Selected Clients"):
            user_query = f"send message to these users: {selected_users}"
            status_placeholder = st.empty()
            response = safe_async_run(stream_agent(user_query, status_placeholder))
            status_placeholder.empty()

            for name in selected_users:
                mark_client_messaged(name)

            st.success("Messages sent successfully!")

    else:
        st.info("No potential clients found.")

    # --- Chat Popup View ---
    if st.session_state["open_chat"]:
        name = st.session_state["open_chat"]
        chats = fetch_chat_history(name)

        st.markdown("---")
        st.markdown(f"## 💬 Chat History with {name}")

        if chats:
            for sender, message, image in chats:
                if image:
                    st.markdown(
                        f"<div style='background-color:#fffbe6; padding:8px; border-radius:5px; margin:4px 0;'>"
                        f"<b>{sender.capitalize()} sent an image:</b></div>",
                        unsafe_allow_html=True
                    )
                    st.image(image)
                else:
                    if sender == "user":
                        st.markdown(
                            f"<div style='background-color:#e6f7ff; padding:8px; border-radius:5px; margin:4px 0;'>"
                            f"<b>User:</b> {message}</div>",
                            unsafe_allow_html=True
                        )
                    else:
                        st.markdown(
                            f"<div style='background-color:#fffbe6; padding:8px; border-radius:5px; margin:4px 0;'>"
                            f"<b>Agent:</b> {message}</div>",
                            unsafe_allow_html=True
                        )
        else:
            st.write("No chat history available.")

        if st.button("Close Chat Window"):
            st.session_state["open_chat"] = None

    # ---------- Divider: AI Agent Interface ----------
    st.divider()
    st.header("Ask the AI Agent")

    if "craftsman_chat_history" not in st.session_state:
        st.session_state["craftsman_chat_history"] = []

    user_query = st.text_input("You:", key="agent_input")

    status_placeholder = st.empty()
    response_placeholder = st.empty()

    if user_query:
        st.session_state["craftsman_chat_history"].append(("user", user_query))

        response = safe_async_run(stream_agent(user_query, status_placeholder))
        st.session_state["craftsman_chat_history"].append(("agent", response))

        status_placeholder.empty()

# ---------------------- Tab 2: Dummy User Interface ----------------------
with tab2:
    st.title("🧵 Chat with Sales Agent")

    st.subheader("Chat History")
    chats = chat_history_user()

    if chats:
        for chat_id, sender, message, image in chats:
            if image:
                st.markdown(
                    f"<div style='background-color:#fffbe6; padding:8px; border-radius:5px; margin:4px 0;'>"
                    f"<b>{sender.capitalize()} sent an image:</b></div>",
                    unsafe_allow_html=True
                )
                st.image(image)
            else:
                if sender == "user":
                    st.markdown(
                        f"<div style='background-color:#e6f7ff; padding:8px; border-radius:5px; margin:4px 0;'>"
                        f"<b>User:</b> {message}</div>",
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown(
                        f"<div style='background-color:#fffbe6; padding:8px; border-radius:5px; margin:4px 0;'>"
                        f"<b>Agent:</b> {message}</div>",
                        unsafe_allow_html=True
                    )
    else:
        st.write("No chat history available.")

    st.subheader("Send Message to Agent")

    user_query1 = st.text_input(" ", key="dummy_input")

    if user_query1:
        user_query_dummy = f"Hardik Sharma replied with: {user_query1}"
        status_placeholder = st.empty()

        agent_response = safe_async_run(stream_agent(user_query_dummy, status_placeholder))
        status_placeholder.empty()
        st.markdown("Message sent. Please refresh.")

    if st.button("🔄 Reset Chat"):
        reset_chat_history_preserve_first()
        st.success("Chat reset!")
