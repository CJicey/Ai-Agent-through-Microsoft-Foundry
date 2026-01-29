from azure.identity import InteractiveBrowserCredential
from azure.ai.projects import AIProjectClient
from dotenv import load_dotenv
from pathlib import Path
import os

print("Running InteractiveBrowserCredential")
def main():
    # Clear console
    os.system("cls" if os.name == "nt" else "clear")

    # Always load .env from this script folder
    script_dir = Path(__file__).resolve().parent
    load_dotenv(script_dir / ".env")

    project_endpoint = os.getenv("PROJECT_ENDPOINT")
    model_deployment = os.getenv("MODEL_DEPLOYMENT_NAME")

    if not project_endpoint or not model_deployment:
        raise RuntimeError("Missing PROJECT_ENDPOINT or MODEL_DEPLOYMENT_NAME in .env")

    # Load data.txt from the same folder as this script
    data_path = script_dir / "data.txt"
    if not data_path.exists():
        raise FileNotFoundError(f"Missing data file: {data_path}")

    data = data_path.read_text(encoding="utf-8")

    print("\n=== DATA LOADED ===")
    print(data)
    print("==================\n")

    # Auth using browser login
    credential = InteractiveBrowserCredential()

    # Creates Azure AI Project client + OpenAI client
    project_client = AIProjectClient(
        endpoint=project_endpoint,
        credential=credential,
    )
    client = project_client.get_openai_client()

    while True:
        prompt = input("Enter a prompt (or type 'quit' to exit): ").strip()

        if prompt.lower() == "quit":
            break

        if not prompt:
            print("Please enter a prompt.")
            continue

        print("\n--- SENDING REQUEST TO AZURE ---")

        try:
            response = client.responses.create(
                model=model_deployment,
                input=(
                    "You are given this CSV data:\n\n"
                    f"{data}\n\n"
                    "Answer the following question clearly and directly:\n\n"
                    f"{prompt}\n"
                ),
            )
        except Exception as e:
            print("\nRequest failed with exception:")
            print(e)
            print()
            continue

        output_text = getattr(response, "output_text", None)

        if output_text and str(output_text).strip():
            print()
            print("Response received:")
            print("--- ANSWER ---")
            print(output_text)
            print("-------------\n")
        else:
            print("No output_text found. (Response printed above.)\n")

if __name__ == "__main__":
    main()


