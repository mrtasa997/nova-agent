import os
import json
import subprocess
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL")
)
MODEL = os.getenv("LLM_MODEL")

# ========== الأدوات ==========
def write_file(filename, content, **kwargs):
    os.makedirs("projects", exist_ok=True)
    path = os.path.join("projects", filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"✅ تم كتابة {filename}"

def read_file(filename, **kwargs):
    path = os.path.join("projects", filename)
    if not os.path.exists(path):
        return f"❌ الملف {filename} غير موجود"
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def run_python(filename, **kwargs):
    path = os.path.join("projects", filename)
    try:
        result = subprocess.run(
            ["python", path],
            capture_output=True, text=True, timeout=10
        )
        return f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    except Exception as e:
        return f"❌ خطأ: {str(e)}"

def list_files():
    if not os.path.exists("projects"):
        return "المجلد فاضي"
    return "\n".join(os.listdir("projects"))

# ========== تعريف الأدوات للـ LLM ==========
tools = [
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "اكتب ملف كود جديد",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string"},
                    "content": {"type": "string"}
                },
                "required": ["filename", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "اقرأ محتوى ملف",
            "parameters": {
                "type": "object",
                "properties": {"filename": {"type": "string"}},
                "required": ["filename"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_python",
            "description": "شغّل ملف بايثون وشوف النتيجة",
            "parameters": {
                "type": "object",
                "properties": {"filename": {"type": "string"}},
                "required": ["filename"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "اعرض كل الملفات في مجلد projects",
            "parameters": {"type": "object", "properties": {}}
        }
    }
]

# ========== سجل تنفيذ الأدوات ==========
TOOL_FUNCTIONS = {
    "write_file": write_file,
    "read_file": read_file,
    "run_python": run_python,
    "list_files": list_files,
}

# ========== حلقة الـ Agent ==========
def run_agent(user_request, max_iterations=5):
    messages = [
        {
            "role": "system",
            "content": (
                "أنت مبرمج محترف. تستطيع كتابة ملفات، قراءتها، وتشغيلها. "
                "لما يطلب منك المستخدم شي، نفّذه خطوة خطوة. "
                "إذا شغّلت كود وطلع خطأ، صلّح الملف تلقائياً."
            )
        },
        {"role": "user", "content": user_request}
    ]
    
    for i in range(max_iterations):
        print(f"\n🔄 الدورة {i+1}...")
        
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )
        
        msg = response.choices[0].message
        messages.append(msg)
        
        # إذا ما طلب أداة → خلص
        if not msg.tool_calls:
            print(f"\n💬 الرد النهائي:\n{msg.content}")
            return
        
        # نفّذ كل أداة طلبها
        for tool_call in msg.tool_calls:
            name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)
            
            print(f"🔧 ينفذ: {name}({list(args.keys())})")
            
            result = TOOL_FUNCTIONS[name](**args)
            print(f"   ↳ {result[:200]}")
            
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": str(result)
            })

# ========== الطلب ==========
if __name__ == "__main__":
    request = "سوي لعبة حجرة ورقة مقص بالبايثون، وبعدها شغلها للتأكد إنها تشتغل"
    run_agent(request)