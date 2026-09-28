import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL")
)

MODEL = os.getenv("LLM_MODEL")

tools = [
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "اكتب كود في ملف جديد",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "اسم الملف"},
                    "content": {"type": "string", "description": "محتوى الملف"}
                },
                "required": ["filename", "content"]
            }
        }
    }
]

def write_file(filename, content):
    os.makedirs("projects", exist_ok=True)
    path = os.path.join("projects", filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"✅ تم إنشاء {filename}"

def run_agent(user_request):
    messages = [
        {"role": "system", "content": "أنت مبرمج محترف. لما يطلب منك المستخدم برنامج، استخدم أداة write_file لإنشاء الملف. اكتب الكود كامل."},
        {"role": "user", "content": user_request}
    ]
    
    print("\n🤔 أفكر...\n")
    
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=tools,
        tool_choice="auto"
    )
    
    msg = response.choices[0].message
    
    if msg.tool_calls:
        for tool_call in msg.tool_calls:
            args = json.loads(tool_call.function.arguments)
            result = write_file(**args)
            print(result)
    else:
        print(msg.content)

# ✅ الطلب مباشرة هنا — بدل input()
request = "سوي لي لعبة تخمين رقم بالبايثون"
run_agent(request)