import os
import json
import datetime
import pytz
print("✓ os and json imported successfully")

try:
    import gdown
    print("✓ gdown imported successfully")
except ImportError as e:
    print(f"✗ Failed to import gdown: {e}")

try:
    from openai import OpenAI
    print("✓ openai imported successfully")
except ImportError as e:
    print(f"✗ Failed to import openai: {e}")

try:
    from pypdf import PdfReader
    print("✓ pypdf imported successfully")
except ImportError as e:
    print(f"✗ Failed to import pypdf: {e}")

try:
    import gradio as gr
    print("✓ gradio imported successfully")
except ImportError as e:
    print(f"✗ Failed to import gradio: {e}")

try:
    from dotenv import load_dotenv
    print("✓ python-dotenv imported successfully")
except ImportError as e:
    print(f"✗ Failed to import python-dotenv: {e}")

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
        self.openai = OpenAI()
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

    def handle_tool_call(self, tool_calls):
        results = []
        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            print(f"Tool called: {tool_name}", flush=True)
            tool = globals().get(tool_name)
            result = tool(**arguments) if tool else {}
            results.append({"role": "tool", "content": json.dumps(result), "tool_call_id": tool_call.id})
        return results

    def system_prompt(self):
        # Get current date and time in EST
        est = pytz.timezone('US/Eastern')
        current_datetime = datetime.datetime.now(est)
        current_date = current_datetime.strftime("%A, %B %d, %Y")
        current_time = current_datetime.strftime("%I:%M %p")
        
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
        
        # Add current date/time context in EST
        system_prompt += f"## Current Context:\n"
        system_prompt += f"Today's date: {current_date}\n"
        system_prompt += f"Current time: {current_time} EST\n"
        system_prompt += f"You should be aware of the current date and time (Eastern Standard Time) when answering questions about availability, scheduling, recent activities, or any time-sensitive matters. "
        system_prompt += f"If someone asks about scheduling or availability, consider the current time and typical business hours.\n\n"
        
        system_prompt += f"With this context, please chat with the user, always staying in character as {self.name}."
        return system_prompt

    def chat(self, message, history):
        messages = [{"role": "system", "content": self.system_prompt()}] + history + [{"role": "user", "content": message}]
        done = False
        while not done:
            response = self.openai.chat.completions.create(model="gpt-4o-mini", messages=messages, tools=tools)
            if response.choices[0].finish_reason == "tool_calls":
                message = response.choices[0].message
                tool_calls = message.tool_calls
                results = self.handle_tool_call(tool_calls)
                messages.append(message)
                messages.extend(results)
            else:
                done = True
        return response.choices[0].message.content


if __name__ == "__main__":
    me = Me()
    port = int(os.environ.get("PORT", 10000))  # Use port 10000 as default for Render
    
    # Custom theme
    dark_theme = gr.themes.Base().set(
        body_background_fill="#2778c4",
        body_text_color="#000000"
    )

    with gr.Blocks(theme=dark_theme) as demo:
        gr.HTML("""
            <style>
                footer, 
                .prose a[href*="gradio.app"], 
                .gradio-container .footer {
                    display: none !important;
                }
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
                type="messages",
                title="Chat with Ibe Nwandu",
                description="Ask me about my background, experience, and skills"
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
        server_name="0.0.0.0",  # Use 0.0.0.0 for Render deployment
        server_port=port,
        share=False,
        show_error=True,
        show_api=False
    )
