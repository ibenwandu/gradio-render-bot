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


# --- Your Me class as before (keep your implementation) ---
class Me:
    def __init__(self):
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is required")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        self.name = "Ibe Nwandu"

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

        summary_txt_url = os.getenv("SUMMARY_TXT_URL")
        summary_txt_path = "summary.txt"
        print(f"Downloading summary text from {summary_txt_url}")
        gdown.download(summary_txt_url, summary_txt_path, quiet=False)

        with open(summary_txt_path, "r", encoding="utf-8") as f:
            self.summary = f.read()

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

    def chat_fn(self, message, history):
        try:
            conversation = []
            for msg in history:
                if msg["role"] == "user":
                    conversation.append({"role": "user", "parts": [msg["content"]]})
                elif msg["role"] == "assistant":
                    conversation.append({"role": "model", "parts": [msg["content"]]})

            conversation.append({"role": "user", "parts": [message]})

            response = self.model.generate_content(
                self.system_prompt() + "\n\n" + message,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7,
                    top_p=0.8,
                    top_k=40,
                    max_output_tokens=2048,
                )
            )
            return response.text

        except Exception as e:
            print(f"Error generating response: {e}")
            return "Sorry, I'm having trouble processing your request right now."


# --- Password logic ---
def toggle_password(show):
    return gr.update(type="text" if show else "password")


def check_password(pw):
    PASSWORD = os.getenv("CHATBOT_PASSCODE")
    if pw == PASSWORD:
        return (
            gr.update(visible=True),   # Show chatbot area
            gr.update(visible=False),  # Hide password input area
            "",                        # Clear error message
        )
    else:
        return (
            gr.update(visible=False),
            gr.update(visible=True),
            "❌ Wrong password. Try again."
        )


# --- Main Interface ---

if __name__ == "__main__":
    me = Me()
    port = int(os.environ.get("PORT", 7860))

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
        </style>
        """)

        error_message = gr.Markdown("", visible=True, interactive=False)
        password_box = gr.Textbox(label="🔑 Enter Access Code", type="password", placeholder="Enter passcode here...")
        show_password_checkbox = gr.Checkbox(label="Show password")
        submit_btn = gr.Button("Submit")

        chatbot_group = gr.Group(visible=False)
        with chatbot_group:
            gr.ChatInterface(
                fn=me.chat_fn,
                chatbot=gr.Chatbot(label="Your Assistant"),
                textbox=gr.Textbox(placeholder="Ask something..."),
                title=None,
                description=None
            )

        gr.HTML("""
        <div style='text-align:center; color:red; padding:1em; font-size:1.2em; font-style:italic;'>
            Ibe Nwandu
        </div>
        """)

        # Events
        show_password_checkbox.change(
            fn=toggle_password,
            inputs=show_password_checkbox,
            outputs=password_box
        )

        submit_btn.click(
            fn=check_password,
            inputs=password_box,
            outputs=[chatbot_group, password_box, error_message]
        )

    demo.launch(
        server_name="0.0.0.0",
        server_port=port,
        share=False,
        show_error=True,
        show_api=False
    )
