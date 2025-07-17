# AI-Powered Client Interaction Assistant

This is a Streamlit-based AI assistant application designed to interact with potential clients using product data and AI models (OpenAI API). The app uses multiple SQLite databases for client management, chat history, and image metadata. Built using Python and Streamlit, it integrates OpenAI's LLM capabilities for generating responses.


## 📂 Project Structure

- `app.py`: Main Streamlit app.
- `agent_handler.py`: Core AI agent logic.
- `function_handler.py`: Database interactions and utility functions.
- `llm_parser.py`: Metadata extraction from images.
- `db.py`: Database initialization and operations.
- `chat_history.db`, `potential_clients.db`, `images.db`, `meesho.db`: SQLite databases storing different layers of project data.

---

## ⚙️ Setup Guide

### 1️⃣ Clone the Repository

```bash
git clone <repository-url>
cd <repository-folder>
```

### 2️⃣ (Recommended) Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate        # On Mac/Linux
# OR
venv\Scripts\activate           # On Windows
```

### 3️⃣ Install Dependencies

```bash
pip install -r requirements.txt
```

### 4️⃣ Set Environment Variables

no need to create .env file 
OPENAI API KEY will be asked to fill once application is run

### 5️⃣ Ensure Databases Exist

Ensure the following SQLite database files are present in your project folder:

- `chat_history.db`
- `potential_clients.db`
- `images.db`
- `meesho.db`

---

## ▶️ Running the Application Locally

```bash
streamlit run app.py
```

- This will launch the Streamlit interface in your web browser.
- Use the provided tabs to upload images or interact with the AI assistant.

