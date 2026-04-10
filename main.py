import os
import httpx
import speech_recognition as sr
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security.api_key import APIKeyHeader
from playwright.sync_api import sync_playwright
from pydub import AudioSegment

app = FastAPI()

# SECURITY: Use the key you set in Render Environment Variables
# If not set, it defaults to 'consulsofnato'
API_KEY = os.environ.get("MY_SOLVER_KEY", "consulsofnato")
api_key_header = APIKeyHeader(name="access_token", auto_error=False)

def verify_key(key: str = Depends(api_key_header)):
    if key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return key

@app.post("/solve_on_page")
def solve_on_page(target_url: str, key: str = Depends(verify_key)):
    mp3_path = "temp.mp3"
    wav_path = "temp.wav"
    
    with sync_playwright() as p:
        # Optimized for Render's 512MB RAM limit
        browser = p.chromium.launch(
            headless=True, 
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        )
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        page = context.new_page()
        
        try:
            # 1. Navigate to the site
            page.goto(target_url, wait_until="networkidle", timeout=60000)
            
            # 2. Find and click the reCAPTCHA checkbox
            # We use a broader selector to ensure we find the iframe
            captcha_frame = page.frame_locator("iframe[title*='reCAPTCHA']").first
            captcha_frame.locator(".recaptcha-checkbox-border").click()
            page.wait_for_timeout(3000)

            # 3. Click the Audio button in the challenge frame
            challenge_frame = page.frame_locator("iframe[title*='challenge']").first
            challenge_frame.locator("#recaptcha-audio-button").click()
            page.wait_for_timeout(2000)

            # 4. Get the Audio Download URL
            audio_url = challenge_frame.locator("#audio-source").get_attribute("src")
            if not audio_url:
                return {"status": "error", "message": "Could not find audio source URL."}

            # 5. Download the audio file
            with httpx.Client() as client:
                resp = client.get(audio_url)
                with open(mp3_path, "wb") as f:
                    f.write(resp.content)
            
            # 6. Convert to WAV (SpeechRecognition requirement)
            audio = AudioSegment.from_mp3(mp3_path)
            audio.export(wav_path, format="wav")

            # 7. AI Voice-to-Text
            recognizer = sr.Recognizer()
            with sr.AudioFile(wav_path) as source:
                audio_data = recognizer.record(source)
                solution = recognizer.recognize_google(audio_data)

            # 8. Type solution and Verify
            challenge_frame.locator("#audio-response").fill(solution)
            challenge_frame.locator("#recaptcha-verify-button").click()
            page.wait_for_timeout(2000)

            return {
                "status": "success", 
                "solution": solution,
                "url_processed": target_url
            }

        except Exception as e:
            return {"status": "error", "message": str(e)}
        
        finally:
            # Cleanup files and browser
            browser.close()
            for f in [mp3_path, wav_path]:
                if os.path.exists(f):
                    os.remove(f)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)
                    
