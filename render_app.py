import os
import json
import gdown
import google.generativeai as genai
from pypdf import PdfReader
import gradio as gr
from dotenv import load_dotenv

print("Loading .env file...")
env_loaded = load_dotenv(override=True)
print(f"Environment file loaded: {env_loaded}")
print(f"Current working directory: {os.getcwd()}")
print(f".env file exists: {os.path.exists('.env')}")

# List all environment variables that start with our expected prefixes
import os
env_vars = {k: v for k, v in os.environ.items() if k.startswith(('GOOGLE_', 'LINKEDIN_', 'SUMMARY_', 'PUSHOVER_', 'CHATBOT_'))}
print(f"Relevant environment variables found: {list(env_vars.keys())}")


def push(text):
    import requests
    requests.post(
        "https://api.pushover.net/1/messages.json",
        data={
            "token": os.getenv("PUSHOVER_TOKEN"),
            "user": os.getenv("PUSHOVER_USER"),
            "message": text,
        }
    )


def record_user_details(email, name="Name not provided", notes="not provided"):
    push(f"Recording {name} with email {email} and notes {notes}")
    return {"recorded": "ok"}


def record_unknown_question(question):
    push(f"Recording {question}")
    return {"recorded": "ok"}


record_user_details_json = {
    "name": "record_user_details",
    "description": "Use this tool to record that a user is interested in being in touch and provided an email address",
    "parameters": {
        "type": "object",
        "properties": {
            "email": {"type": "string", "description": "The email address of this user"},
            "name": {"type": "string", "description": "The user's name, if they provided it"},
            "notes": {"type": "string", "description": "Any additional information about the conversation that's worth recording to give context"},
        },
        "required": ["email"],
        "additionalProperties": False,
    },
}

record_unknown_question_json = {
    "name": "record_unknown_question",
    "description": "Always use this tool to record any question that couldn't be answered as you didn't know the answer",
    "parameters": {
        "type": "object",
        "properties": {
            "question": {"type": "string", "description": "The question that couldn't be answered"},
        },
        "required": ["question"],
        "additionalProperties": False,
    },
}

# Define tools for Gemini using function declaration format
tools = [
    genai.protos.Tool(
        function_declarations=[
            genai.protos.FunctionDeclaration(
                name="record_user_details",
                description="Use this tool to record that a user is interested in being in touch and provided an email address",
                parameters=genai.protos.Schema(
                    type=genai.protos.Type.OBJECT,
                    properties={
                        "email": genai.protos.Schema(type=genai.protos.Type.STRING, description="The email address of this user"),
                        "name": genai.protos.Schema(type=genai.protos.Type.STRING, description="The user's name, if they provided it"),
                        "notes": genai.protos.Schema(type=genai.protos.Type.STRING, description="Any additional information about the conversation that's worth recording to give context"),
                    },
                    required=["email"]
                )
            ),
            genai.protos.FunctionDeclaration(
                name="record_unknown_question",
                description="Always use this tool to record any question that couldn't be answered as you didn't know the answer",
                parameters=genai.protos.Schema(
                    type=genai.protos.Type.OBJECT,
                    properties={
                        "question": genai.protos.Schema(type=genai.protos.Type.STRING, description="The question that couldn't be answered"),
                    },
                    required=["question"]
                )
            )
        ]
    )
]


class Me:
    def __init__(self):
        # Debug environment variables
        print("Checking environment variables...")
        print(f"GOOGLE_API_KEY exists: {bool(os.getenv('GOOGLE_API_KEY'))}")
        print(f"LINKEDIN_PDF_URL: {os.getenv('LINKEDIN_PDF_URL')}")
        print(f"SUMMARY_TXT_URL: {os.getenv('SUMMARY_TXT_URL')}")
        
        # Configure Google Gemini API
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is required")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash', tools=tools)
        self.name = "Ibe Nwandu"

        # Try to load files - first check if they exist locally, then try to download
        linkedin_pdf_path = "linkedin.pdf"
        
        if os.path.exists(linkedin_pdf_path):
            print(f"Using existing LinkedIn PDF: {linkedin_pdf_path}")
        else:
            # Download linkedin.pdf using gdown
            linkedin_pdf_url = os.getenv("LINKEDIN_PDF_URL")
            if not linkedin_pdf_url:
                raise ValueError("LINKEDIN_PDF_URL environment variable is required and linkedin.pdf not found locally")
            
            # Handle both full URLs and file IDs
            if linkedin_pdf_url.startswith("http"):
                download_url = linkedin_pdf_url
            else:
                # Assume it's a file ID and construct the URL
                download_url = f"https://drive.google.com/uc?id={linkedin_pdf_url}"
            
            print(f"Downloading LinkedIn PDF from {download_url}")
            try:
                gdown.download(download_url, linkedin_pdf_path, quiet=False)
            except Exception as e:
                print(f"Failed to download LinkedIn PDF: {e}")
                print("Please ensure the Google Drive file is shared with 'Anyone with the link' permissions")
                print("Or place the linkedin.pdf file directly in the project directory")
                raise

        # Read LinkedIn PDF
        with open(linkedin_pdf_path, "rb") as f:
            header = f.read(5)
        print(f"PDF header bytes: {header}")

        reader = PdfReader(linkedin_pdf_path)
        self.linkedin = ""
        for page in reader.pages:
            text = page.extract_text()
            if text:
                self.linkedin += text

        # Try to load summary file
        summary_txt_path = "summary.txt"
        
        if os.path.exists(summary_txt_path):
            print(f"Using existing summary file: {summary_txt_path}")
        else:
            # Download summary.txt using gdown
            summary_txt_url = os.getenv("SUMMARY_TXT_URL")
            if not summary_txt_url:
                raise ValueError("SUMMARY_TXT_URL environment variable is required and summary.txt not found locally")
            
            # Handle both full URLs and file IDs
            if summary_txt_url.startswith("http"):
                download_url = summary_txt_url
            else:
                # Assume it's a file ID and construct the URL
                download_url = f"https://drive.google.com/uc?id={summary_txt_url}"
                
            print(f"Downloading summary text from {download_url}")
            try:
                gdown.download(download_url, summary_txt_path, quiet=False)
            except Exception as e:
                print(f"Failed to download summary file: {e}")
                print("Please ensure the Google Drive file is shared with 'Anyone with the link' permissions")
                print("Or place the summary.txt file directly in the project directory")
                raise

        with open(summary_txt_path, "r", encoding="utf-8") as f:
            self.summary = f.read()

    def handle_tool_call(self, function_call):
        """Handle function calls from Gemini"""
        function_name = function_call.name
        function_args = function_call.args
        
        print(f"Tool called: {function_name}", flush=True)
        
        if function_name == "record_user_details":
            result = record_user_details(
                email=function_args.get("email", ""),
                name=function_args.get("name", "Name not provided"),
                notes=function_args.get("notes", "not provided")
            )
        elif function_name == "record_unknown_question":
            result = record_unknown_question(
                question=function_args.get("question", "")
            )
        else:
            result = {"error": f"Unknown function: {function_name}"}
        
        return genai.protos.Part(
            function_response=genai.protos.FunctionResponse(
                name=function_name,
                response={"result": json.dumps(result)}
            )
        )

    def system_prompt(self):
        system_prompt = (
            f"You are acting as {self.name}. You are answering questions on {self.name}'s website, "
            f"particularly questions related to {self.name}'s career, background, skills and experience. "
            f"Your responsibility is to represent {self.name} for interactions on the website as faithfully as possible. "
            f"You are given a summary of {self.name}'s background and LinkedIn profile which you can use to answer questions. "
            f"Be professional and engaging, as if talking to a potential client or future employer who came across the website. "
            f"If you don't know the answer to any question, use your record_unknown_question tool to record the question that you couldn't answer, even if it's about something trivial or unrelated to career. "
            f"If the user is engaging in discussion, try to steer them towards getting in touch via email; ask for their email and record it using your record_user_details tool. "
        )
        system_prompt += f"\n\n## Summary:\n{self.summary}\n\n## LinkedIn Profile:\n{self.linkedin}\n\n"
        system_prompt += f"With this context, please chat with the user, always staying in character as {self.name}."
        return system_prompt

    def chat(self, message, history):
        """Chat method that properly handles Gemini conversation flow with Gradio"""
        try:
            print(f"Received message: {message}")
            print(f"History length: {len(history) if history else 0}")
            
            # Create a new chat session
            chat = self.model.start_chat()
            
            # Build the conversation context
            conversation_parts = []
            
            # Add system prompt for the first message
            if not history:
                conversation_parts.append(self.system_prompt())
            
            # Add conversation history
            if history:
                for msg in history:
                    if msg["role"] == "user":
                        conversation_parts.append(f"User: {msg['content']}")
                    elif msg["role"] == "assistant":
                        conversation_parts.append(f"Assistant: {msg['content']}")
            
            # Add current user message
            conversation_parts.append(f"User: {message}")
            
            # Combine all parts
            full_message = "\n\n".join(conversation_parts)
            
            print(f"Sending to Gemini: {full_message[:200]}...")
            
            # Send message to Gemini
            response = chat.send_message(
                full_message,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7,
                    top_p=0.8,
                    top_k=40,
                    max_output_tokens=2048,
                )
            )
            
            print(f"Gemini response received")
            
            # Handle function calls if present
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'function_call') and part.function_call:
                        print(f"Function call detected: {part.function_call.name}")
                        # Handle the function call
                        function_response = self.handle_tool_call(part.function_call)
                        
                        # Send function response and get final response
                        final_response = chat.send_message(
                            function_response,
                            generation_config=genai.types.GenerationConfig(
                                temperature=0.7,
                                top_p=0.8,
                                top_k=40,
                                max_output_tokens=2048,
                            )
                        )
                        
                        # Extract text from final response
                        if hasattr(final_response, 'text'):
                            response_text = final_response.text
                        else:
                            response_text = str(final_response)
                        
                        print(f"Final response: {response_text[:100]}...")
                        return response_text
            
            # Get the text response
            if hasattr(response, 'text'):
                response_text = response.text
            else:
                response_text = str(response)
            
            print(f"Response: {response_text[:100]}...")
            return response_text
            
        except Exception as e:
            print(f"Error in chat: {e}")
            import traceback
            traceback.print_exc()
            return "I apologize, but I'm having trouble processing your request right now. Please try again."


if __name__ == "__main__":
    me = Me()
    port = int(os.environ.get("PORT", 7861))  # Use port 7861 instead of 7860
    
    # Custom theme
    dark_theme = gr.themes.Base().set(
        body_background_fill="#2778c4",
        body_text_color="#000000"
    )

    with gr.Blocks(theme=dark_theme) as demo:
        gr.HTML("""
        <style>
            footer { display: none !important; }
            .svelte-1ipelgc { display: none !important; }
            .prose a[href*="gradio.app"] { display: none !important; }
            .gradio-container .prose { display: none !important; }
            .gradio-container .footer { display: none !important; }
            .gradio-container .center { margin-bottom: 0 !important; }
        </style>
        """)

        # Password section - always visible initially
        with gr.Column(visible=True) as password_section:
            gr.Markdown("# Welcome")
            error_message = gr.Textbox(
                value="", 
                visible=False, 
                interactive=False, 
                show_label=False,
                container=False
            )
            password_box = gr.Textbox(
                label="🔑 Enter Access Code", 
                type="password",
                placeholder="Enter password to access chatbot"
            )
            with gr.Row():
                submit_btn = gr.Button("Submit", variant="primary")
                show_password_btn = gr.Button("👁️ Show", variant="secondary")

        # Container for chatbot that starts hidden
        with gr.Column(visible=False) as chatbot_section:
            chatbot_interface = gr.ChatInterface(
                fn=me.chat,
                title="Chat with Ibe Nwandu",
                description="Ask me about my background, experience, and skills",
                type="messages"
            )

        # Footer
        gr.HTML("""
        <div style='text-align:center; color:red; padding:1em; font-size:1.2em; font-style:italic;'>
            Ibe Nwandu
        </div>
        """)

        # Show/hide password toggle
        password_visible = gr.State(False)
        
        def toggle_password_visibility(is_visible):
            new_visible = not is_visible
            if new_visible:
                return gr.update(type="text"), "🙈 Hide", new_visible
            else:
                return gr.update(type="password"), "👁️ Show", new_visible

        # Button logic
        def handle_password_submit(pw):
            PASSWORD = os.getenv("CHATBOT_PASSCODE")
            if pw == PASSWORD:
                return (
                    gr.update(visible=False),  # Hide password section completely
                    gr.update(visible=True),   # Show chatbot section
                    gr.update(value="", visible=False)  # Clear and hide error
                )
            else:
                return (
                    gr.update(visible=True),   # Keep password section visible
                    gr.update(visible=False),  # Keep chatbot hidden
                    gr.update(value="❌ Wrong password. Try again.", visible=True)  # Show error
                )

        submit_btn.click(
            fn=handle_password_submit,
            inputs=password_box,
            outputs=[password_section, chatbot_section, error_message]
        )
        
        show_password_btn.click(
            fn=toggle_password_visibility,
            inputs=password_visible,
            outputs=[password_box, show_password_btn, password_visible]
        )

    # Launch app
    demo.launch(
        server_name="127.0.0.1",  # Use localhost instead of 0.0.0.0
        server_port=port,
        share=False,
        show_error=True,
        show_api=False
    )