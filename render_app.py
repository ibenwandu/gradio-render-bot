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
        self.linkedin = "".join(page.extract_text() or "" for page in reader.pages)

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
        prompt = (
            f"You are acting as {self.name} on {self.name}'s website. Answer questions related to career, skills, "
            f"background, and represent {self.name} faithfully. "
            f"Use the summary and LinkedIn info provided. "
            f"Use `record_unknown_question` tool when unsure, and try to collect user's email with `record_user_details`.\n\n"
        )
        prompt += f"## Summary:\n{self.summary}\n\n## LinkedIn Profile:\n{self.linkedin}\n\n"
        return prompt

    def chat_fn(self, message, history):
        try:
            chat = self.model.start_chat(history=[])
            conversation = [
                {"role": msg["role"], "parts": [msg["content"]]} if msg["role"] == "user"
                else {"role": "model", "parts": [msg["content"]]} for msg in history
            ]
            conversation.append({"role": "user", "parts": [message]})
            response = self.model.generate_content(
                self.system_prompt() + "\n\n" + message,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7, top_p=0.8, top_k=40, max_output_tokens=2048,
                )
            )
            return response.text
        except Exception as e:
            print(f"Error generating response: {e}")
            return "Sorry, I'm having trouble processing your request right now."


# -------------------------------
# Password Toggle and Verification
# -------------------------------

def toggle_password(show):
    return gr.update(type="text" if show else "password")

def verify_passcode(input_passcode):
    if input_passcode == os.getenv("CHATBOT_PASSCODE"):
        return gr.update(visible=False), gr.update(visible=True)
    else:
        return gr.update(value="", label="Incorrect passcode, try again:"), gr.update(visible=False)


# -------------------------------
# Build and Launch the Interface
# -------------------------------

if __name__ == "__main__":
    me = Me()

    with gr.Blocks() as demo:
        # Modal-style Login View
        with gr.Column(visible=True) as login_view:
            gr.Markdown("### 🔐 Enter Passcode to Access Chatbot")

            pass_input = gr.Textbox(
                label="Passcode",
                type="password",
                placeholder="Enter passcode...",
                show_label=True
            )

            show_pw_checkbox = gr.Checkbox(label="Show password")

            pass_submit = gr.Button("Submit")

            # Toggle visibility of password field
            show_pw_checkbox.change(
                fn=toggle_password,
                inputs=show_pw_checkbox,
                outputs=pass_input
            )

        # Chatbot View (Initially Hidden)
        with gr.ChatInterface(
            fn=me.chat_fn,
            visible=False,
            chatbot=gr.Chatbot(label="Your Assistant"),
            textbox=gr.Textbox(placeholder="Ask something..."),
        ) as chat_view:
            pass

        # Handle Submit
        pass_submit.click(
            fn=verify_passcode,
            inputs=pass_input,
            outputs=[login_view, chat_view]
        )

    demo.launch(
        server_name="0.0.0.0",
        share=False,
        show_error=True,
        show_api=False,
        server_port=int(os.environ.get("PORT", 7860))
    )
