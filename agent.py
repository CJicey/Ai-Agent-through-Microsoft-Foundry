from azure.identity import InteractiveBrowserCredential
from azure.ai.projects import AIProjectClient
from dotenv import load_dotenv
from pathlib import Path
import streamlit as st
import pandas as pd
import subprocess
import sys
import os

# ---------- Auto-launch in Streamlit ----------
# Relaunch this script with Streamlit when run directly, avoiding infinite loops.
if __name__ == "__main__" and not os.environ.get("STREAMLIT_RUN"):
    os.environ["STREAMLIT_RUN"] = "1"
    subprocess.run([
        sys.executable, "-m", "streamlit", "run", Path(__file__).name 
    ])
    sys.exit()

# ---------- Helpers ----------
def load_env():
    # Load .env from the script directory so local config works consistently.
    script_dir = Path(__file__).resolve().parent
    load_dotenv(script_dir / ".env")

    # Read required Azure AI Project settings.
    project_endpoint = os.getenv("PROJECT_ENDPOINT")
    model_deployment = os.getenv("MODEL_DEPLOYMENT_NAME")

    # Stop early if required configuration is missing.
    if not project_endpoint or not model_deployment:
        raise RuntimeError("Missing PROJECT_ENDPOINT or MODEL_DEPLOYMENT_NAME in .env")
    else:
        print("Loaded PROJECT_ENDPOINT and MODEL_DEPLOYMENT_NAME from .env")

    return project_endpoint, model_deployment


def load_excel_sheets(excel_file) -> dict[str, pd.DataFrame]:
    # Load every sheet from the Excel file into a DataFrame dictionary.
    return pd.read_excel(excel_file, sheet_name=None)


def sheets_to_csv_text(sheets: dict[str, pd.DataFrame], max_rows_per_sheet: int = 300) -> str:
    # Convert all sheets into a single CSV-style string while limiting row count.
    data = ""
    for sheet_name, df in sheets.items():
        data += f"\n--- SHEET: {sheet_name} (first {max_rows_per_sheet} rows) ---\n"
        data += df.head(max_rows_per_sheet).to_csv(index=False)
    return data


@st.cache_resource
def get_client(project_endpoint: str):
    # Cache the authenticated Azure client so login only happens once.
    credential = InteractiveBrowserCredential()
    project_client = AIProjectClient(endpoint=project_endpoint, credential=credential)
    return project_client.get_openai_client()


def apply_bp_branding():
    # Applies Bennett & Pless branding with a logo and light Streamlit styling.
    script_dir = Path(__file__).resolve().parent

    candidates = [
        script_dir / "assets" / "B&P.png",
    ]
    logo_path = next((p for p in candidates if p.exists()), None)

    # Add small CSS tweaks to improve spacing and rounded UI elements.
    st.markdown(
        """
        <style>
          .block-container { padding-top: 1.1rem; }
          [data-testid="stSidebar"] .block-container { padding-top: 1rem; }
          .stButton > button { border-radius: 10px; padding: 0.6rem 1rem; font-weight: 600; }
          .stChatMessage { border-radius: 14px; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Display logo if available, otherwise fall back to text.
    col1, col2 = st.columns([1, 7], vertical_alignment="center")
    with col1:
        if logo_path is not None:
            try:
                st.image(logo_path.read_bytes(), use_container_width=True)
            except Exception:
                st.markdown("### B&P")
        else:
            st.markdown("### B&P")

    st.markdown("---")


# ---------- UI ----------
# Configure the Streamlit page before rendering anything.
st.set_page_config(page_title="RFQ Scanner", layout="wide")
apply_bp_branding()

# Main page title and description.
st.title("RFQ Scanner Chatbot")
st.caption("Ask questions about the uploaded Excel data using your Azure AI Project deployment.")

# Load Azure configuration from the .env file.
project_endpoint, model_deployment = load_env()


# ---------- Sidebar ----------
# Sidebar controls for selecting the Excel data source.
st.sidebar.header("Bennett & Pless — Data Source")
st.sidebar.caption("Upload an Excel file or use a local data.xlsx file.")
uploaded = st.sidebar.file_uploader("Upload an Excel file (.xlsx)", type=["xlsx", "xls"])


# ---------- Data Loading ----------
# Use uploaded file if provided, otherwise fall back to a local data.xlsx file.
if uploaded:
    st.sidebar.success(f"Loaded: {uploaded.name}")
    sheets = load_excel_sheets(uploaded)
else:
    script_dir = Path(__file__).resolve().parent
    local_path = script_dir / "data.xlsx"
    if not local_path.exists():
        st.sidebar.warning("Upload an Excel file, or place data.xlsx next to this script.")
        st.stop()
    sheets = load_excel_sheets(local_path)

# Convert Excel data to a text format suitable for model input.
data_text = sheets_to_csv_text(sheets, max_rows_per_sheet=300)


# ---------- Data Preview ----------
# Allow users to preview Excel sheets in a readable table format.
with st.expander("Preview Excel (readable)"):
    sheet_names = list(sheets.keys())
    selected_sheet = st.selectbox("Choose a sheet", sheet_names)

    # Control how many rows and columns are shown in the preview.
    max_rows = st.slider("Rows to show", min_value=10, max_value=500, value=100, step=10)
    all_cols = list(sheets[selected_sheet].columns)
    default_cols = all_cols[: min(8, len(all_cols))]
    show_cols = st.multiselect("Columns to show (optional)", options=all_cols, default=default_cols)

    df_preview = sheets[selected_sheet]
    if show_cols:
        df_preview = df_preview[show_cols]

    st.dataframe(df_preview.head(max_rows), use_container_width=True)

    st.caption(
        f"Showing first {min(max_rows, len(sheets[selected_sheet]))} rows of '{selected_sheet}'. "
        "Only the first 300 rows per sheet are sent to the model."
    )


# ---------- Chat ----------
# Initialize the Azure OpenAI client (triggers browser login on first run).
client = get_client(project_endpoint)

# Store chat history across Streamlit reruns.
if "messages" not in st.session_state:
    st.session_state.messages = []

st.subheader("Chat")

# Render previous chat messages.
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# Input field for user questions.
user_prompt = st.chat_input("How can I help you today?")

if user_prompt:
    # Save and display the user's message.
    st.session_state.messages.append({"role": "user", "content": user_prompt})
    with st.chat_message("user"):
        st.markdown(user_prompt)

    # Send the question and data to the model.
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                response = client.responses.create(
                    model=model_deployment,
                    input=(
                        "You are given this CSV data:\n\n"
                        f"{data_text}\n\n"
                        "Answer the following question clearly and directly:\n\n"
                        f"{user_prompt}\n"
                    ),
                )
                output_text = getattr(response, "output_text", None) or "No output_text returned."
            except Exception as e:
                output_text = f"Request failed:\n\n{e}"

        # Display and store the assistant response.
        st.markdown(output_text)
        st.session_state.messages.append({"role": "assistant", "content": output_text})



