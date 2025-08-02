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

tools = [
    {"type": "function", "function": record_user_details_json},
    {"type": "function", "function": record_unknown_question_json},
]


class Me:
    def __init__(self):
        # Configure Google Gemini API
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is required")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        self.name = "Ibe Nwandu"

        # Download linkedin.pdf using gdown
        linkedin_pdf_url = os.getenv("LINKEDIN_PDF_URL")
        linkedin_pdf_path = "linkedin.pdf"
        print(f"Downloading LinkedIn PDF from {linkedin_pdf_url}")
        gdown.download(linkedin_pdf_url, linkedin_pdf_path, quiet=True)

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
        gdown.download(summary_txt_url, summary_txt_path, quiet=True)

        with open(summary_txt_path, "r", encoding="utf-8") as f:
            self.summary = f.read()

    def handle_tool_call(self, tool_calls):
        results = []
        for tool_call in tool_calls:
            tool_name = tool_call.name
            arguments = json.loads(tool_call.args)
            print(f"Tool called: {tool_name}", flush=True)
            tool = globals().get(tool_name)
            result = tool(**arguments) if tool else {}
            results.append(f"Tool {tool_name} result: {json.dumps(result)}")
        return "\n".join(results)

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
        # Build conversation context for Google Generative AI
        system_prompt = self.system_prompt()
        
        # Create conversation history for context
        conversation_text = ""
        if history:
            for msg in history:
                if msg.role == "user":
                    conversation_text += f"User: {msg.content}\n"
                elif msg.role == "assistant":
                    conversation_text += f"Ibe: {msg.content}\n\n"
        
        # Combine system prompt, conversation history, and current message
        full_prompt = f"{system_prompt}\n\n{conversation_text}User: {message}\nIbe:"
        
        # Generate response with tools
        try:
            response = self.model.generate_content(
                full_prompt,
                tools=tools,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.8,
                    top_p=0.9,
                    top_k=50,
                    max_output_tokens=2048,
                )
            )
            
            # Handle tool calls if present
            if response.candidates[0].finish_reason == "STOP":
                return response.text
            elif response.candidates[0].finish_reason == "SAFETY":
                return "I apologize, but I cannot respond to that request."
            else:
                # Handle tool calls
                try:
                    tool_calls = response.candidates[0].content.parts[0].function_calls
                    if tool_calls:
                        results = self.handle_tool_call(tool_calls)
                        # Generate final response after tool calls
                        final_response = self.model.generate_content(
                            f"{full_prompt}\n\nTool results: {results}\n\nIbe:",
                            generation_config=genai.types.GenerationConfig(
                                temperature=0.8,
                                top_p=0.9,
                                top_k=50,
                                max_output_tokens=2048,
                            )
                        )
                        return final_response.text
                    else:
                        return response.text
                except AttributeError:
                    # No function calls found, return the response text
                    return response.text
                    
        except Exception as e:
            print(f"Error generating response: {e}")
            return "I apologize, but I'm having trouble processing your request right now. Please try again."
    

import os
import gradio as gr



if __name__ == "__main__":
    me = Me()
    port = int(os.environ.get("PORT", 7860))
    PASSWORD = os.getenv("CHATBOT_PASSCODE")

        # Custom theme
    dark_theme = gr.themes.Base().set(
        body_background_fill="#2778c4",
        body_text_color="#000000"
    )

with gr.Blocks(theme=dark_theme) as demo:
    # Define functions inside the blocks context
    def check_password(pw):
        if pw == PASSWORD:
            return (
                gr.update(visible=True),   # Show chatbot area
                gr.update(visible=False),  # Hide password input
                gr.update(visible=False),  # Hide checkbox
                gr.update(visible=False),  # Hide submit button
                ""                         # Clear error
            )
        else:
            return (
                gr.update(visible=False),
                gr.update(visible=True),
                gr.update(visible=True),
                gr.update(visible=True),
                "❌ Wrong password. Try again."
            )

    def toggle_password_visibility(show):
        return gr.update(type="text" if show else "password")
    gr.HTML("""
    <style>
        footer { display: none !important; }
        .svelte-1ipelgc { display: none !important; }
        .prose a[href*="gradio.app"] { display: none !important; }
    </style>
    """)

    error_message = gr.Textbox(visible=False, interactive=False, show_label=False)
    password_box = gr.Textbox(label="🔑 Enter Access Code", type="password")
    show_password_checkbox = gr.Checkbox(label="Show password")
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

    # Show/hide password logic
    show_password_checkbox.change(
        fn=toggle_password_visibility,
        inputs=show_password_checkbox,
        outputs=password_box
    )

    # Button logic
    submit_btn.click(
        fn=check_password,
        inputs=password_box,
        outputs=[chatbot_group, password_box, show_password_checkbox, submit_btn, error_message]
    )

# Launch app
demo.launch(
    server_name="0.0.0.0",
    share=False,
    show_error=True,
    show_api=False
) 