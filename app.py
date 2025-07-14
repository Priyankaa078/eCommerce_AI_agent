import streamlit as st
import sqlite3
import asyncio
import openai
from db import init_db, save_image_with_metadata, get_images_with_metadata
from llm_parser import extract_metadata_from_image
from agent_handler import ask_agent 
from function_handler import (
    fetch_chat_history, fetch_clients, fetch_messaged_clients,
    mark_client_messaged, chat_history_user, reset_chat_history_preserve_first
)

#  Prompt user for their OpenAI API key
st.sidebar.header("API Configuration")
user_api_key = st.sidebar.text_input(
    "Enter your OpenAI API Key",
    type="password"
)

if user_api_key:
    st.session_state["OPENAI_API_KEY"] = user_api_key
    openai.api_key = user_api_key
else:
    st.warning("Please enter your OpenAI API key to continue.")
    st.stop()


init_db()

st.set_page_config(page_title="Sales Agent", layout="centered")
tab1, tab2 = st.tabs(["Craftsman interface", "Dummy user interface"])

# ---------------------- Tab 1: Craftsman Interface ----------------------
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
            message_to_agent = f"send message to these users: {selected_users}"
            response = asyncio.run(ask_agent(message_to_agent))

            for name in selected_users:
                mark_client_messaged(name)

            st.success("Messages sent successfully!")

    else:
        st.info("No potential clients found.")

    # --- Chat Popup View ---
    if st.session_state["open_chat"]:
        name = st.session_state["open_chat"]
        chat_history = fetch_chat_history(name)

        st.markdown("---")
        st.markdown(f"## 💬 Chat History with {name}")

        if chat_history:
            st.markdown(
                "<div style='height:300px; overflow-y: scroll; border:1px solid #ccc; padding:10px; background:#fafafa'>"
                + "".join(
                    f"<p><b>{sender.capitalize()}:</b> {message}</p>"
                    for sender, message in chat_history
                )
                + "</div>",
                unsafe_allow_html=True
            )
        else:
            st.info(f"No chat history found for {name}.")

        if st.button("Close Chat Window"):
            st.session_state["open_chat"] = None

    # ---------- Divider: AI Agent Interface ----------
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

# ---------------------- Tab 2: Dummy User Interface ----------------------
with tab2:
    st.title("🧵 Chat with Sales Agent")

    st.subheader("Chat History")
    chats = chat_history_user()
    if chats:
        for chat_id, sender, message in chats:
            if sender == "user":
                st.markdown(f"<div style='background-color:#e6f7ff; padding:8px; border-radius:5px; margin:4px 0;'>"
                        f"<b>User:</b> {message}</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div style='background-color:#fffbe6; padding:8px; border-radius:5px; margin:4px 0;'>"
                        f"<b>Agent:</b> {message}</div>", unsafe_allow_html=True)
    else:
        st.info("No chat history yet.")

    st.subheader("Send Message to Agent")

    user_query = st.text_input(" ", key="dummy_input")

    if user_query:
        formatted_query = f"Hardik Sharma replied with: {user_query}"

        st.markdown(f"**You:** {user_query}")

        with st.spinner("sending..."):
            agent_response = asyncio.run(ask_agent(formatted_query))
            st.markdown(f"**Agent:** {agent_response}")

    # Reset chat button

    if st.button("🔄 Reset Chat"):
        reset_chat_history_preserve_first()
        st.success("Chat reset!")
