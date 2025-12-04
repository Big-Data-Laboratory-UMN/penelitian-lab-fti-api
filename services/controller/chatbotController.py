import torch
import numpy as np
from typing import List, Optional, Tuple, Dict, Any
import httpx
from datetime import datetime, timedelta
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from transformers import AutoTokenizer, AutoModelForCausalLM

from services.database import SessionLocal
from services.models.KnowledgeBaseModel import knowledge_base

# ---------- Global State ----------
kb: List[dict] = []
tfidf: Optional[TfidfVectorizer] = None
tfidf_matrix = None
contexts: List[str] = []
tokenizer = None
model = None
device = "cpu"

# ---------- Load KB ----------
def load_kb():
    global kb, contexts, tfidf, tfidf_matrix
    session = SessionLocal()
    try:
        # Using SQLAlchemy model
        rows = session.query(knowledge_base).all()
        kb = []
        contexts = []
        for r in rows:
            # Map model fields (vcategory, vcontext, vanswer) to dict
            # Handle potential None values if necessary, though model implies nullable=True
            cat = r.vcategory if r.vcategory else ""
            ctx = r.vcontext if r.vcontext else ""
            ans = r.vanswer if r.vanswer else ""
            
            kb.append({"category": cat, "context": ctx, "answer": ans})
            if ctx:
                contexts.append(ctx.lower())
        
        print(f"[SUCCESS] Loaded {len(kb)} KB entries")
        if contexts:
            tfidf = TfidfVectorizer(lowercase=True)
            tfidf_matrix = tfidf.fit_transform(contexts)
            print(f"[SUCCESS] TF-IDF matrix built ({len(contexts)} entries)")
    except Exception as e:
        print(f"[ERROR] DB: {e}")
        kb = []
    finally:
        session.close()

# ---------- Retrieval ----------
def retrieve_kb(query: str, threshold: float = 0.15) -> Tuple[Optional[dict], float]:
    if tfidf is None or tfidf_matrix is None or len(kb) == 0:
        return None, 0.0
    
    q = query.lower()
    q_vec = tfidf.transform([q])
    sims = cosine_similarity(q_vec, tfidf_matrix).flatten()
    
    for i, ctx in enumerate(contexts):
        if any(word in q for word in ctx.split(",")):
            sims[i] += 0.4
    
    best_idx = np.argmax(sims)
    best_score = float(sims[best_idx])
    
    if best_score >= threshold:
        return kb[best_idx], best_score
    return None, 0.0

# ---------- Load GPT-2 ----------
def load_gpt2():
    global tokenizer, model, device
    # Adjust path: services/controller/chatbotController.py -> services/controller -> services -> root -> chatbot/fine_tuned_fti
    # Original: services/api/chatbotAPI.py -> services/api -> services -> root
    # Both are 3 levels deep from root if we consider 'services' as top level in the package structure, 
    # but physically:
    # api/chatbotAPI.py is in services/api
    # controller/chatbotController.py is in services/controller
    # So the relative path logic should be the same: parent.parent.parent
    
    BASE_DIR = Path(__file__).parent.parent.parent
    model_path = BASE_DIR / "chatbot" / "fine_tuned_fti"

    if model_path.exists() and model_path.is_dir():
        try:
            print(f"[SUCCESS] Model ditemukan di: {model_path}")
            tokenizer = AutoTokenizer.from_pretrained(str(model_path))
            model = AutoModelForCausalLM.from_pretrained(str(model_path))
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token
            device = "cuda" if torch.cuda.is_available() else "cpu"
            model.to(device).eval()
            print(f"[SUCCESS] GPT-2 berhasil di-load di {device}!")
        except Exception as e:
            print(f"[ERROR] Gagal load GPT-2: {e}")
            model = None

# ---------- Generate Santai (ANTI-HALU) ----------
def generate_santai(context: str, question: str) -> str:
    if not model or not tokenizer:
        return context.strip()

    prompt = f"""Kamu LabBot UMN yang ramah dan santai.
Jawab HANYA dari info ini, singkat aja (max 2-3 kalimat):

{context}

Pertanyaan: {question}

Jawaban santai:"""

    try:
        inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=400).to(device)
        with torch.no_grad():
            output = model.generate(
                **inputs,
                max_new_tokens=80,
                temperature=0.4,
                top_p=0.85,
                do_sample=True,
                repetition_penalty=3.0,
                pad_token_id=tokenizer.eos_token_id,
                eos_token_id=tokenizer.eos_token_id,
            )
        full_text = tokenizer.decode(output[0], skip_special_tokens=True)
        jawaban = full_text.split("Jawaban santai:")[-1].strip()
        jawaban = jawaban.split("\n")[0].strip()

        if len(jawaban) > 180 or len(jawaban) < 8 or "saya adalah" in jawaban.lower():
            return context.strip()
        return jawaban
    except Exception as e:
        print(f"[Generation error] {e}")
        return context.strip()

# ========== FITUR SLOT KOSONG PER HARI (PAKAI /by-month + BYPASS AUTH) ==========
async def get_bookings_by_month(year: int, month: int):
    try:
        async with httpx.AsyncClient() as client:
            headers = {"X-Chatbot-Secret": "umnfti2025gacor"}  # ← ini kunci rahasia
            url = f"http://127.0.0.1:8000/booking/by-month?month={month}&year={year}"
            r = await client.get(url, headers=headers, timeout=10.0)
            if r.status_code == 200:
                return r.json()  # list booking
    except Exception as e:
        print(f"[SLOT ERROR] {e}")
    return []

def get_empty_slots_on_date(target_date: datetime, bookings: list) -> str:
    booked = set()
    target_str = target_date.strftime("%Y-%m-%d")
    
    for b in bookings:
        if b.get("booking_date", "").startswith(target_str) and b.get("status") == 1:
            start = b["start_time"][:5]
            end = b["end_time"][:5]
            booked.add(f"{start}-{end}")
    
    all_slots = ["08:00-10:00", "10:00-12:00", "13:00-15:00", "15:00-17:00", "17:00-19:00"]
    empty = [s for s in all_slots if s not in booked]
    
    if not empty:
        return "Full semua bro!"
    return ", ".join(empty) if empty else "Full"

# ---------- Main Logic ----------
async def process_chat(message: str) -> Dict[str, Any]:
    msg = message.strip()
    if not msg:
        raise ValueError("Pesan kosong!")

    msg_lower = msg.lower()

    # ========== DETEKSI HARI ==========
    hari_map = {
        "senin": 0, "selasa": 1, "rabu": 2, "kamis": 3,
        "jumat": 4, "sabtu": 5, "minggu": 6
    }
    detected_day = None
    for nama_hari, weekday in hari_map.items():
        if nama_hari in msg_lower:
            detected_day = nama_hari.capitalize()
            break

    if detected_day and any(k in msg_lower for k in ["kosong", "slot", "jadwal", "jam", "ada"]):
        today = datetime.now()
        target_weekday = hari_map[detected_day.lower()]
        days_ahead = (target_weekday - today.weekday() + 7) % 7
        if days_ahead == 0:
            days_ahead = 7  # minggu depan kalau hari ini
        target_date = today + timedelta(days=days_ahead)
        
        bookings = await get_bookings_by_month(target_date.year, target_date.month)
        slots = get_empty_slots_on_date(target_date, bookings)
        
        return {
            "response": f"Slot kosong hari {detected_day} ({target_date.day}/{target_date.month}):\n{slots}",
            "category": "jadwal_hari",
            "score": 1.0
        }

    # ========== HARI INI ==========
    if any(k in msg_lower for k in ["hari ini", "sekarang", "kosong", "slot", "jadwal"]):
        today = datetime.now()
        bookings = await get_bookings_by_month(today.year, today.month)
        slots = get_empty_slots_on_date(today, bookings)
        
        return {
            "response": f"Slot kosong hari ini ({today.day}/{today.month}):\n{slots}",
            "category": "jadwal_hari_ini",
            "score": 1.0
        }

    # ========== KB + Model ==========
    entry, score = retrieve_kb(msg)
    if entry:
        jawaban = generate_santai(entry["answer"], msg)
        return {"response": jawaban, "category": entry["category"], "score": round(score, 3)}

    # ========== Greeting ==========
    if any(g in msg_lower for g in ["halo","hi","pagi","siang","sore","hai","helo","assalam"]):
        return {
            "response": "Halo bro/sis! LabBot FTI UMN siap bantu! Mau tanya SOP lab, pinjam alat, atau slot kosong?",
            "category": "greeting",
            "score": 1.0
        }

    # ========== Fallback ==========
    return {
        "response": "Maaf aku belum nemu infonya di SOP resmi. Coba tanya koordinator lab ya!",
        "score": 0.0
    }

def get_health_status() -> Dict[str, Any]:
    return {
        "status": "LabBot UMN AKTIF 100%!",
        "kb_entries": len(kb),
        "gpt2_loaded": model is not None,
        "tfidf_ready": tfidf is not None,
        "timestamp": datetime.now().strftime("%d %b %Y %H:%M")
    }

def startup_chatbot():
    load_kb()
    load_gpt2()
    print("LabBot FTI UMN SIAP PAKAI MODEL + KB + SLOT HARI APAPUN!")
