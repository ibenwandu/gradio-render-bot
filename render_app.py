import os
import json
import gdown
import google.generativeai as genai
from pypdf import PdfReader
import gradio as gr
from dotenv import load_dotenv

load_dotenv(override=True)


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
        # Configure Google Gemini API
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is required")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash', tools=tools)
        self.name = "Ibe Nwandu"

        # Download linkedin.pdf using gdown
        linkedin_pdf_url = os.getenv("LINKEDIN_PDF_URL")
        linkedin_pdf_path = "linkedin.pdf"
        print(f"Downloading LinkedIn PDF from {linkedin_pdf_url}")
        gdown.download(linkedin_pdf_url, linkedin_pdf_path, quiet=False)

        with open(linkedin_pdf_path, "rb") as f:
            header = f.read(5)
        print(f"PDF header bytes: {header}")

        reader = PdfReader(linkedin_pdf_path)
        self.linkedin = ""
        for page in reader.pages:
            text = page.extract_text()
            if text:
                self.linkedin += text

        # Download summary.txt using gdown
        summary_txt_url = os.getenv("SUMMARY_TXT_URL")
        summary_txt_path = "summary.txt"
        print(f"Downloading summary text from {summary_txt_url}")
        gdown.download(summary_txt_url, summary_txt_path, quiet=False)

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
        """Chat method that properly handles Gemini conversation flow like OpenAI"""
        try:
            # Convert Gradio history to Gemini format
            gemini_history = []
            
            # Add system prompt as first user message (Gemini doesn't have system role)
            gemini_history.append({
                "role": "user", 
                "parts": [self.system_prompt()]
            })
            gemini_history.append({
                "role": "model", 
                "parts": ["I understand. I'm ready to represent Ibe Nwandu professionally and help answer questions about his background and experience."]
            })
            
            # Convert history from Gradio format to Gemini format
            for msg in history:
                if msg["role"] == "user":
                    gemini_history.append({"role": "user", "parts": [msg["content"]]})
                elif msg["role"] == "assistant":
                    gemini_history.append({"role": "model", "parts": [msg["content"]]})
            
            # Start chat with history
            chat = self.model.start_chat(history=gemini_history)
            
            # Send current message and handle tool calls like OpenAI does
            done = False
            current_message = message
            
            while not done:
                response = chat.send_message(
                    current_message,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.7,
                        top_p=0.8,
                        top_k=40,
                        max_output_tokens=2048,
                    )
                )
                
                # Check if the response contains function calls
                if response.candidates[0].content.parts:
                    has_function_calls = any(
                        hasattr(part, 'function_call') and part.function_call 
                        for part in response.candidates[0].content.parts
                    )
                    
                    if has_function_calls:
                        # Handle function calls
                        function_responses = []
                        for part in response.candidates[0].content.parts:
                            if hasattr(part, 'function_call') and part.function_call:
                                function_response = self.handle_tool_call(part.function_call)
                                function_responses.append(function_response)
                        
                        # Send function responses back to continue conversation
                        if function_responses:
                            current_message = function_responses
                        else:
                            done = True
                    else:
                        done = True
                else:
                    done = True
            
            # Return the final text response
            return response.text
            
        except Exception as e:
            print(f"Error generating response: {e}")
            return "I apologize, but I'm having trouble processing your request right now. Please try again."


def check_password(pw):
    PASSWORD = os.getenv("CHATBOT_PASSCODE")
    if pw == PASSWORD:
        return (
            gr.update(visible=True),   # Show chatbot area
            gr.update(visible=False),  # Hide password input
            ""                         # Clear error
        )
    else:
        return (
            gr.update(visible=False),
            gr.update(visible=True),
            "❌ Wrong password. Try again."
        )


if __name__ == "__main__":
    me = Me()
    port = int(os.environ.get("PORT", 7860))
    
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

        error_message = gr.Textbox(visible=False, interactive=False, show_label=False)
        password_box = gr.Textbox(label="🔑 Enter Access Code", type="password")
        submit_btn = gr.Button("Submit")

        # Container for chatbot that can be hidden
        chatbot_group = gr.Group(visible=False)
        with chatbot_group:
            gr.ChatInterface(
                fn=me.chat,
                title=None,
                description=None,
                type="messages"
            )

        # Footer
        gr.HTML("""
        <div style='text-align:center; color:red; padding:1em; font-size:1.2em; font-style:italic;'>
            Ibe Nwandu
        </div>
        """)

        # Button logic
        submit_btn.click(
            fn=check_password,
            inputs=password_box,
            outputs=[chatbot_group, password_box, error_message]
        )

    # Launch app
    demo.launch(
        server_name="0.0.0.0",
        share=False,
        show_error=True,
        show_api=False
    )