"""
LLM Analysis Quiz Solution Backend – TDS Spec Compliant
Enhanced with timeout protection, retry logic, and improved CSV detection
"""

import os
import asyncio
import re
import io
import time
from typing import Optional, Any, Dict
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from playwright.async_api import async_playwright
import httpx
import pandas as pd
import requests
from PyPDF2 import PdfReader
from openai import OpenAI

# Load environment variables
load_dotenv()

AIPIPE_TOKEN = os.getenv("AIPIPE_TOKEN")
EXPECTED_SECRET = os.getenv("QUIZ_SECRET", "quiz-secret-2025")
# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PORT = int(os.getenv("PORT", 5000))

if not AIPIPE_TOKEN:
    raise ValueError("AIPIPE_TOKEN not found in .env!")

# if not OPENAI_API_KEY:
#     print("⚠️ WARNING: OPENAI_API_KEY not found. Audio/Vision will fail!")

app = FastAPI(
    title="LLM Quiz API Solver – TDS",
    description="Auto solves TDS LLM quiz tasks",
    version="3.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic Models
class QuizRequest(BaseModel):
    email: str
    secret: str
    url: str

class QuizResponse(BaseModel):
    correct: Optional[bool]
    url: Optional[str]
    reason: Optional[str]
    details: Optional[Any]


# Health Check Endpoints
@app.get("/")
async def root():
    return {
        "status": "ok",
        "message": "LLM Quiz Auto-Solver API",
        "version": "3.1.0"
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}


# Secret validation
def check_secret(secret: str) -> bool:
    return secret.strip() == EXPECTED_SECRET


# IMPROVEMENT 3: Retry logic for failed requests
async def fetch_with_retry(url: str, max_retries: int = 3, timeout: int = 30) -> requests.Response:
    """Fetch URL with retry logic"""
    for attempt in range(max_retries):
        try:
            print(f"📥 Fetching {url} (attempt {attempt + 1}/{max_retries})")
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                print(f"❌ Failed after {max_retries} attempts: {str(e)}")
                raise
            wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
            print(f"⚠️ Attempt {attempt + 1} failed, retrying in {wait_time}s...")
            await asyncio.sleep(wait_time)


# IMPROVEMENT 2: Enhanced Audio Handler with better CSV detection

async def handle_audio_task(page, html: str, text_content: str) -> str:
    """Handle audio transcription with optional CSV analysis"""
    try:
        # Find audio element or link
        audio_match = re.search(r'<audio[^>]+src="([^"]+)"', html)
        if not audio_match:
            audio_match = re.search(r'href="([^"]+\.(?:mp3|wav|m4a|ogg|opus))"', html)
        
        if not audio_match:
            return "NO_AUDIO_FOUND"
        
        audio_url = audio_match.group(1)
        if not audio_url.startswith('http'):
            if not audio_url.startswith('/'):
                audio_url = '/' + audio_url
            audio_url = "https://tds-llm-analysis.s-anand.net" + audio_url
        
        print(f"🎵 Audio: {audio_url}")
        
        # Download audio with retry
        audio_resp = await fetch_with_retry(audio_url)
        
        temp_audio = 'temp_audio.mp3'
        with open(temp_audio, 'wb') as f:
            f.write(audio_resp.content)
        
        # Transcribe with AI Pipe (using requests - simpler)
        print("🎙️ Transcribing audio...")
        with open(temp_audio, 'rb') as audio_file:
            files = {'file': (temp_audio, audio_file, 'audio/mpeg')}
            data = {'model': 'whisper-1'}
            headers = {'Authorization': f'Bearer {AIPIPE_TOKEN}'}
            
            response = requests.post(
                'https://aipipe.org/openai/v1/audio/transcriptions',
                files=files,
                data=data,
                headers=headers,
                timeout=60
            )
            response.raise_for_status()
            result = response.json()
            transcription = result.get('text', '').strip()
        
        print(f"📝 Transcription: {transcription}")
        
        # Clean up temp file
        if os.path.exists(temp_audio):
            os.remove(temp_audio)
        
        # Check for CSV in combined task
        if '.csv' in html:
            csv_match = re.search(r'href="([^"]+\.csv)"', html)
            if csv_match:
                csv_url = csv_match.group(1)
                if not csv_url.startswith('http'):
                    if not csv_url.startswith('/'):
                        csv_url = '/' + csv_url
                    csv_url = "https://tds-llm-analysis.s-anand.net" + csv_url
                
                cutoff_match = re.search(r'[Cc]utoff[:\s]+(\d+)', text_content)
                cutoff = int(cutoff_match.group(1)) if cutoff_match else None
                
                print(f"📊 CSV: {csv_url}, Cutoff: {cutoff}")
                
                csv_resp = await fetch_with_retry(csv_url)
                df = pd.read_csv(io.StringIO(csv_resp.text))
                
                print(f"📋 CSV columns: {list(df.columns)}")
                print(f"📋 CSV shape: {df.shape}")
                
                if cutoff:
                    value_col = None
                    for col in ['value', 'Value', 'VALUE']:
                        if col in df.columns:
                            value_col = col
                            break
                    
                    if not value_col:
                        for col in df.columns:
                            if 'value' in col.lower():
                                value_col = col
                                break
                    
                    if not value_col:
                        numeric_cols = df.select_dtypes(include=['number']).columns
                        value_col = numeric_cols[0] if len(numeric_cols) > 0 else None
                    
                    if value_col:
                        filtered = df[df[value_col] > cutoff]
                        count = len(filtered)
                        filtered_sum = filtered[value_col].sum() if len(filtered) > 0 else 0
                        
                        print(f"✅ Filtered {count} rows above {cutoff}, sum: {filtered_sum}")
                        answer = str(int(filtered_sum))
                    else:
                        print("⚠️ No numeric column found")
                        answer = transcription
                else:
                    answer = f"{transcription}. CSV rows: {len(df)}"
                
                return answer
        
        return transcription
    
    except Exception as e:
        print(f"❌ Audio error: {str(e)}")
        return f"AUDIO_ERROR: {str(e)}"


# Main Quiz Solver Function
async def solve_quiz(payload: dict) -> dict:
    """Main function to solve quiz tasks"""
    url = payload["url"]
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)

            html = await page.content()
            text_content = await page.inner_text("body")
            
            print(f"\n🎯 URL: {url}")
            
            answer = None
            
            # === TASK ROUTING ===
            
            # 1. DEMO
            if url.endswith('/demo') or ('demo' in url and 'scrape' not in url and 'audio' not in url):
                print("✅ DEMO task")
                answer = "test123"
            
            # 2. SCRAPING
            elif 'scrape' in url and 'audio' not in url:
                print("✅ SCRAPING task")
                
                scrape_link = await page.query_selector('a[href*="scrape-data"]')
                if scrape_link:
                    scrape_url = await scrape_link.get_attribute('href')
                    if not scrape_url.startswith('http'):
                        scrape_url = "https://tds-llm-analysis.s-anand.net" + scrape_url
                    
                    print(f"🔍 Scraping: {scrape_url}")
                    
                    await page.goto(scrape_url, wait_until="networkidle", timeout=30000)
                    await asyncio.sleep(1)
                    
                    answer = (await page.inner_text("body")).strip()
                    print(f"📋 Content: {answer}")
                else:
                    match = re.search(r'(https?://[^\s]+/demo-scrape-data[^\s"<>]+)', html)
                    if match:
                        scrape_url = match.group(1)
                        # Use retry logic
                        scrape_resp = await fetch_with_retry(scrape_url)
                        answer = scrape_resp.text.strip()
                    else:
                        answer = "NO_SCRAPE_URL"
            
            # 3. AUDIO
            elif 'audio' in url or '<audio' in html or '.mp3' in html:
                print("✅ AUDIO task")
                answer = await handle_audio_task(page, html, text_content)
            
            # 4. CSV (standalone)
            elif '.csv' in html and 'audio' not in html:
                print("✅ CSV task")
                
                csv_match = re.search(r'href="([^"]+\.csv)"', html)
                if csv_match:
                    csv_url = csv_match.group(1)
                    if not csv_url.startswith('http'):
                        csv_url = "https://tds-llm-analysis.s-anand.net" + csv_url
                    
                    print(f"📊 CSV: {csv_url}")
                    
                    # Use retry logic
                    csv_resp = await fetch_with_retry(csv_url)
                    df = pd.read_csv(io.StringIO(csv_resp.text))
                    
                    if 'sum' in text_content.lower():
                        col_match = re.search(r'"([^"]+)"\s+column', text_content)
                        if col_match and col_match.group(1) in df.columns:
                            answer = str(df[col_match.group(1)].sum())
                        else:
                            numeric_cols = df.select_dtypes(include=['number']).columns
                            answer = str(df[numeric_cols[0]].sum()) if len(numeric_cols) > 0 else "NO_NUMERIC"
                    
                    elif 'cutoff' in text_content.lower():
                        cutoff_match = re.search(r'[Cc]utoff[:\s]+(\d+)', text_content)
                        if cutoff_match:
                            cutoff = int(cutoff_match.group(1))
                            numeric_cols = df.select_dtypes(include=['number']).columns
                            if len(numeric_cols) > 0:
                                answer = str(len(df[df[numeric_cols[0]] > cutoff]))
                            else:
                                answer = str(len(df))
                        else:
                            answer = str(len(df))
                    else:
                        answer = str(len(df))
                else:
                    answer = "NO_CSV_FOUND"
            
            # 5. PDF
            elif '.pdf' in html:
                print("✅ PDF task")
                
                pdf_match = re.search(r'href="([^"]+\.pdf)"', html)
                if pdf_match:
                    pdf_url = pdf_match.group(1)
                    if not pdf_url.startswith('http'):
                        pdf_url = "https://tds-llm-analysis.s-anand.net" + pdf_url
                    
                    print(f"📄 PDF: {pdf_url}")
                    
                    # Use retry logic
                    pdf_resp = await fetch_with_retry(pdf_url)
                    reader = PdfReader(io.BytesIO(pdf_resp.content))
                    
                    page_match = re.search(r'page\s+(\d+)', text_content, re.IGNORECASE)
                    page_num = int(page_match.group(1)) - 1 if page_match else 1
                    
                    if page_num < len(reader.pages):
                        text = reader.pages[page_num].extract_text()
                        
                        if 'sum' in text_content.lower():
                            numbers = re.findall(r'\d+', text)
                            answer = str(sum(map(int, numbers))) if numbers else "NO_NUMBERS"
                        else:
                            answer = text.strip()[:500]
                    else:
                        answer = "INVALID_PAGE"
                else:
                    answer = "NO_PDF_FOUND"
            
            # 6. IMAGE/VISION
            elif '.jpg' in html or '.png' in html or 'image' in text_content.lower():
                print("✅ IMAGE task")
                
                img_match = re.search(r'(?:src|href)="([^"]+\.(?:jpg|png|jpeg|gif))"', html, re.IGNORECASE)
                if img_match:
                    img_url = img_match.group(1)
                    if not img_url.startswith('http'):
                        img_url = "https://tds-llm-analysis.s-anand.net" + img_url
                    
                    print(f"🖼️ Image: {img_url}")
                    
                    client = OpenAI( 
                        api_key=AIPIPE_TOKEN,
                        base_url="https://aipipe.org/openai/v1/"
                    ) 
                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[{
                            "role": "user",
                            "content": [
                                {"type": "text", "text": f"Answer this question about the image: {text_content[:500]}"},
                                {"type": "image_url", "image_url": {"url": img_url}}
                            ]
                        }],
                        max_tokens=500
                    )
                    answer = response.choices[0].message.content
                else:
                    answer = "NO_IMAGE_FOUND"
            
            # 7. FALLBACK
            else:
                print("⚠️ Unknown task type, using fallback")
                answer = "test123"
            
            await browser.close()
            
            # Submit answer
            submit_url = "https://tds-llm-analysis.s-anand.net/submit"
            submit_payload = {
                "email": payload["email"],
                "secret": payload["secret"],
                "url": payload["url"],
                "answer": answer
            }
            
            print(f"📤 Submitting: {submit_payload}")
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(submit_url, json=submit_payload)
                resp.raise_for_status()
                result = resp.json()
                print(f"✅ Response: {result}")
                return result
        
        except Exception as e:
            await browser.close()
            print(f"❌ Error in solve_quiz: {str(e)}")
            raise e
# IMPROVEMENT 1: Chain Solver with timeout protection
async def solve_quiz_chain(payload: dict, max_steps: int = 10):
    """Solve multiple quizzes in sequence with timeout protection"""
    all_results = []
    current_payload = payload.copy()
    start_time = time.time()
    TIMEOUT = 180  # 3 minutes total
    
    for step in range(max_steps):
        # Check timeout
        elapsed = time.time() - start_time
        if elapsed > TIMEOUT:
            print(f"⏱️ Timeout reached after {step} steps ({elapsed:.1f}s)")
            break
        
        print(f"\n{'='*60}")
        print(f"STEP {step+1}/{max_steps}: {current_payload['url']}")
        print(f"⏱️ Elapsed time: {elapsed:.1f}s / {TIMEOUT}s")
        print('='*60)
        
        try:
            result = await solve_quiz(current_payload)
            all_results.append(result)
            
            # Check if we should continue
            if result.get("url"): 
                current_payload["url"] = result["url"] # Check if there's a next URL (regardless of correct/incorrect)
    
                if result.get("correct", False):
                    print(f"✅ Step {step+1} passed, continuing to next URL")
                else:
                    print(f"⚠️ Step {step+1} failed but continuing to next URL: {result.get('reason', 'No reason')}")
            else:
                # No more URLs to process
                if result.get("correct", False):
                    print(f"✅ Quiz chain completed successfully after {step+1} steps")
                else:
                    print(f"❌ Step {step+1} failed with no next URL: {result.get('reason', 'No reason')}")
                break





            # if result.get("correct", False) and result.get("url"):
            #     current_payload["url"] = result["url"]
            #     print(f"✅ Step {step+1} passed, continuing to next URL")
            # else:
            #     if not result.get("correct", False):
            #         print(f"❌ Step {step+1} failed: {result.get('reason', 'No reason provided')}")
            #     else:
            #         print(f"✅ Quiz chain completed successfully after {step+1} steps")
            #     break
        
        except Exception as e:
            print(f"❌ Error at step {step+1}: {str(e)}")
            all_results.append({
                "correct": False,
                "reason": f"Exception: {str(e)}",
                "url": None
            })
            break
    
    total_time = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"🏁 Chain completed: {len(all_results)} steps in {total_time:.1f}s")
    print('='*60)
    
    return all_results


# API Endpoints
@app.post("/solve-quiz-chain")
async def solve_quiz_chain_endpoint(payload: Dict[str, Any]):
    """Solve a chain of quiz tasks"""
    if not check_secret(payload.get("secret", "")):
        raise HTTPException(status_code=403, detail="Invalid secret")
    
    try:
        results = await solve_quiz_chain(payload, max_steps=10)
        return {"results": results}
    except Exception as e:
        print(f"❌ Chain endpoint error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Error: {str(e)}")


@app.post("/solve-quiz")
async def solve_quiz_endpoint(payload: Dict[str, Any]):
    """Solve a single quiz task"""
    if not check_secret(payload.get("secret", "")):
        raise HTTPException(status_code=403, detail="Invalid secret")
    
    try:
        result = await solve_quiz(payload)
        return result
    except Exception as e:
        print(f"❌ Single quiz endpoint error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Error: {str(e)}")


# Main entry point
if __name__ == "__main__":
    import uvicorn
    print("="*70)
    print(f"🚀 Starting LLM Quiz Solver v3.1.0")
    print(f"🌐 Server: http://0.0.0.0:{PORT}")
    print(f"📋 Health: http://localhost:{PORT}/health")
    print("="*70)
    print("\n📝 Test command:")
    print(f"curl -X POST http://localhost:{PORT}/solve-quiz-chain \\")
    print(f'  -H "Content-Type: application/json" \\')
    print(f'  -d \'{{')
    print(f'    "email":"21f1003507@ds.study.iitm.ac.in",')
    print(f'    "secret":"quiz-secret-2025",')
    print(f'    "url":"https://tds-llm-analysis.s-anand.net/demo"')
    print(f'  }}\'')
    print("\n" + "="*70 + "\n")
    
    uvicorn.run("app:app", host="0.0.0.0", port=PORT, reload=True)
