import streamlit as st
from db import init_db , save_image_with_metadata , get_images_with_metadata
from agent_handler import ask_agent
from llm_parser import extract_metadata_from_image

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
        type = ["jpg" , "jpeg" ,"png"],
        accept_multiple_files =True
    )

    if uploaded_files:
        for file in uploaded_files:
            image_bytes = file.read()
            with st.spinner("Analyzing with AI..."):
                metadata = extract_metadata_from_image(image_bytes)
            save_image_with_metadata(file.name , image_bytes ,metadata)
            st.success(f"{file.name} saved with metadata")

        st.subheader("Stored Handicrafts")
        for name , img_blob ,metadata in get_images_with_metadata():
            st.image(img_blob,caption=name , use_container_width=True)
            st.json(metadata)

#Placeholder
with tab2:
    st.header("Ask the AI agent")
    
    if "chat_history" not in st.session_state:
        st.session_state.chat_history =[]

    user_input = st.text_input("You:" ,key = "agent_input")

    if user_input:
        st.session_state.chat_history.append(("user" , user_input))
        with st.spinner("Thinking..."):
            response = ask_agent(user_input)
        st.session_state.chat_history.append(("agent" , response))

    for role , message in st.session_state.chat_history:
        st.markdown(f"**{role.capitalize()}:** {message}")
