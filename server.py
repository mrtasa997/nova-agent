import os
import json
import subprocess
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL")
)
MODEL = os.getenv("LLM_MODEL")

# ========== الأدوات ==========
def write_file(filename, content, **kwargs):
    os.makedirs("projects", exist_ok=True)
    path = os.path.join("projects", filename)
    os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(path) else None
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"OK كتبت {filename}"

def read_file(filename, **kwargs):
    path = os.path.join("projects", filename)
    if not os.path.exists(path):
        return f"الملف {filename} غير موجود"
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def run_python(filename, **kwargs):
    path = os.path.join("projects", filename)
    try:
        result = subprocess.run(
            ["python", path],
            capture_output=True, text=True, timeout=10,
            input="\n\n\n\n\n"
        )
        if result.returncode != 0:
            return "فشل التشغيل. الخطأ:\n" + result.stderr[:800]
        return "نجح التشغيل. الناتج:\n" + (result.stdout[:500] if result.stdout else "(بلا ناتج)")
    except subprocess.TimeoutExpired:
        return "البرنامج ينتظر إدخال - هذا طبيعي للألعاب التفاعلية"
    except Exception as e:
        return "خطأ: " + str(e)

def install_package(package_name, **kwargs):
    try:
        result = subprocess.run(
            ["pip", "install", package_name],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            return f"تم تثبيت {package_name} بنجاح"
        return f"فشل التثبيت: {result.stderr[:300]}"
    except Exception as e:
        return "خطأ: " + str(e)

def list_files(**kwargs):
    if not os.path.exists("projects"):
        return "فاضي"
    result = []
    for root, dirs, files in os.walk("projects"):
        for f in files:
            result.append(os.path.relpath(os.path.join(root, f), "projects"))
    return "\n".join(result) if result else "فاضي"

TOOL_FUNCTIONS = {
    "write_file": write_file,
    "read_file": read_file,
    "run_python": run_python,
    "install_package": install_package,
    "list_files": list_files,
}

tools = [
    {"type": "function", "function": {"name": "write_file", "description": "اكتب ملف كود جديد", "parameters": {"type": "object", "properties": {"filename": {"type": "string", "description": "اسم الملف مع المسار"}, "content": {"type": "string", "description": "محتوى الملف"}}, "required": ["filename", "content"]}}},
    {"type": "function", "function": {"name": "read_file", "description": "اقرأ ملف موجود", "parameters": {"type": "object", "properties": {"filename": {"type": "string"}}, "required": ["filename"]}}},
    {"type": "function", "function": {"name": "run_python", "description": "شغّل ملف بايثون", "parameters": {"type": "object", "properties": {"filename": {"type": "string"}}, "required": ["filename"]}}},
    {"type": "function", "function": {"name": "install_package", "description": "ثبّت مكتبة بايثون مثل pygame أو flask", "parameters": {"type": "object", "properties": {"package_name": {"type": "string"}}, "required": ["package_name"]}}},
    {"type": "function", "function": {"name": "list_files", "description": "اعرض كل الملفات في مجلد projects", "parameters": {"type": "object", "properties": {}}}},
]

class ChatRequest(BaseModel):
    message: str

SYSTEM_PROMPT = """أنت مبرمج محترف خبير في بايثون.

قواعد أساسية:
1. اكتب كود كامل وجاهز للتشغيل
2. بعد كتابة أي ملف، شغّله بـ run_python
3. إذا فشل التشغيل، اقرأ الخطأ بدقة، صلّح الملف، وشغّله مرة ثانية
4. استمر بالإصلاح حتى ينجح التشغيل
5. إذا احتجت مكتبة، استخدم install_package أولاً
6. للألعاب الرسومية استخدم pygame، وللتطبيقات الرسومية tkinter
7. تأكد من إغلاق كل الأقواس والعلامات
8. في النهاية اشرح للمستخدم شنو سويت بالعربي

مهم جداً:
- لا تتوقف حتى ينجح التشغيل 100%
- إذا فشل التشغيل، صلّح الخطأ فوراً وأعد التشغيل
- استمر بالإصلاح حتى ينجح، ولو احتجت 10 محاولات
- لا تعطي رد نهائي إلا بعد نجاح التشغيل"""

@app.post("/chat")
async def chat(req: ChatRequest):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": req.message}
    ]
    
    logs = []
    for i in range(25):
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )
        msg = response.choices[0].message
        messages.append(msg)
        
        if not msg.tool_calls:
            return {"reply": msg.content, "logs": logs}
        
        for tc in msg.tool_calls:
            name = tc.function.name
            args = json.loads(tc.function.arguments)
            result = TOOL_FUNCTIONS[name](**args)
            logs.append(f"{name} -> {result[:150]}")
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": str(result)
            })
    
    return {"reply": "وصلت للحد الأقصى من الدورات", "logs": logs}

@app.get("/", response_class=HTMLResponse)
async def home():
    if os.path.exists("index.html"):
        with open("index.html", encoding="utf-8") as f:
            return f.read()
    return "<h1>index.html مفقود</h1>"

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)