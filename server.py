import os
import json
import subprocess
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
import zipfile

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
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"OK كتبت {filename}"

def read_file(filename, **kwargs):
    path = os.path.join("projects", filename)
    if not os.path.exists(path):
        return f"الملف {filename} غير موجود"
    with open(path, "r", encoding="utf-8") as f:
        return f.read()[:3000]

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
        return "البرنامج ينتظر إدخال - طبيعي للألعاب التفاعلية"
    except Exception as e:
        return "خطأ: " + str(e)

def install_package(package_name, **kwargs):
    try:
        result = subprocess.run(
            ["pip", "install", package_name],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            return f"تم تثبيت {package_name}"
        return f"فشل التثبيت: {result.stderr[:300]}"
    except Exception as e:
        return "خطأ: " + str(e)

def list_files(**kwargs):
    if not os.path.exists("projects"):
        return "المجلد فاضي - لا يوجد ملفات"
    result = []
    for root, dirs, files in os.walk("projects"):
        for f in files:
            result.append(os.path.relpath(os.path.join(root, f), "projects"))
    return "\n".join(result) if result else "المجلد فاضي - لا يوجد ملفات"

def delete_file(filename, **kwargs):
    path = os.path.join("projects", filename)
    if os.path.exists(path):
        os.remove(path)
        return f"تم حذف {filename}"
    return f"الملف غير موجود"

def create_zip(zip_name="project.zip", **kwargs):
    if not os.path.exists("projects"):
        return "لا يوجد ملفات"
    zip_path = os.path.join("projects", zip_name)
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk("projects"):
            for f in files:
                if f == zip_name:
                    continue
                fp = os.path.join(root, f)
                arc = os.path.relpath(fp, "projects")
                zf.write(fp, arc)
    return f"OK تم إنشاء {zip_name}"

TOOL_FUNCTIONS = {
    "write_file": write_file,
    "read_file": read_file,
    "run_python": run_python,
    "install_package": install_package,
    "list_files": list_files,
    "delete_file": delete_file,
    "create_zip": create_zip,
}

tools = [
    {"type": "function", "function": {"name": "write_file", "description": "اكتب ملف كود جديد بأي لغة", "parameters": {"type": "object", "properties": {"filename": {"type": "string", "description": "اسم الملف مع المسار"}, "content": {"type": "string", "description": "محتوى الملف"}}, "required": ["filename", "content"]}}},
    {"type": "function", "function": {"name": "read_file", "description": "اقرأ ملف موجود", "parameters": {"type": "object", "properties": {"filename": {"type": "string"}}, "required": ["filename"]}}},
    {"type": "function", "function": {"name": "run_python", "description": "شغّل ملف بايثون", "parameters": {"type": "object", "properties": {"filename": {"type": "string"}}, "required": ["filename"]}}},
    {"type": "function", "function": {"name": "install_package", "description": "ثبّت مكتبة بايثون", "parameters": {"type": "object", "properties": {"package_name": {"type": "string"}}, "required": ["package_name"]}}},
    {"type": "function", "function": {"name": "list_files", "description": "اعرض كل الملفات الموجودة في المشروع", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "delete_file", "description": "احذف ملف", "parameters": {"type": "object", "properties": {"filename": {"type": "string"}}, "required": ["filename"]}}},
    {"type": "function", "function": {"name": "create_zip", "description": "اجمع كل الملفات في ZIP للتحميل", "parameters": {"type": "object", "properties": {"zip_name": {"type": "string"}}}}},
]

class ChatRequest(BaseModel):
    message: str

SYSTEM_PROMPT = """أنت NOVA، مساعد ذكي شامل وقوي جداً.

قدراتك:
1. المحادثة العامة: تجيب على أي سؤال بالعربي.
2. البرمجة بكل اللغات: Python, JavaScript, HTML, CSS, Java, C++, PHP, Go, Ruby, SQL.
3. بناء التطبيقات الكاملة: مواقع، APIs، ألعاب، أدوات.
4. الكتابة الإبداعية: مقالات، قصص، قصائد.
5. الترجمة والتلخيص والتحليل.

قواعد مهمة جداً:
1. حدد نوع الطلب أولاً:
   - سؤال محادثة عادي (مثل: ما عاصمة اليابان؟) → جاوب مباشرة بدون استخدام أدوات.
   - طلب برمجة أو ملفات → استخدم الأدوات.

2. للبرمجة:
   - اكتب كود كامل وجاهز.
   - استخدم write_file للكتابة ثم run_python للتشغيل.
   - إذا فشل، صلّح الخطأ وأعد التشغيل حتى ينجح.
   - إذا احتجت مكتبة، استخدم install_package أولاً.

3. لتحليل الملفات (مهم جداً):
   - إذا طلب المستخدم تحليل ملف أو تعديله، استخدم list_files أولاً لتعرف الملفات الموجودة.
   - بعدها استخدم read_file لقراءة الملف المطلوب.
   - حلل المحتوى واشرحه بالتفصيل.
   - لا تقل "لا أرى الملف" قبل ما تجرب list_files.

4. للمشاريع الكاملة:
   - نظّم الملفات بمجلدات (مثل web/index.html).
   - اجمعها بـ create_zip في النهاية.

5. لأي لغة غير بايثون:
   - اكتب الملف فقط.
   - اشرح كيف يشغله المستخدم.

ردك النهائي بالعربي، واضح ومنظم."""

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
            return {"reply": msg.content or "(تم)", "logs": logs}
        
        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments)
                result = TOOL_FUNCTIONS[name](**args)
            except Exception as e:
                result = f"خطأ بالأداة: {str(e)}"
            logs.append(f"{name} -> {result[:200]}")
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": str(result)
            })
    
    return {"reply": "وصلت للحد الأقصى من الدورات", "logs": logs}

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    os.makedirs("projects", exist_ok=True)
    path = os.path.join("projects", file.filename)
    content = await file.read()
    with open(path, "wb") as f:
        f.write(content)
    return {"message": f"تم رفع {file.filename} إلى مجلد projects"}

@app.get("/download/{filename}")
async def download_file(filename: str):
    path = os.path.join("projects", filename)
    if not os.path.exists(path):
        return {"error": "الملف غير موجود"}
    return FileResponse(path, filename=filename)

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