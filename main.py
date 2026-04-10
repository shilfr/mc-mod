import os
import httpx
import speech_recognition as sr
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security.api_key import APIKeyHeader
from playwright.sync_api import sync_playwright
from pydub import AudioSegment

app = FastAPI()

# SECURITY: Set this in Render Env Vars as MY_SOLVER_KEY
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
    captured_token = "TOKEN_NOT_FOUND"
    
    with sync_playwright() as p:
        # Launch with stealth arguments to hide from Discord's bot detection
        browser = p.chromium.launch(
            headless=True, 
            args=[
                "--no-sandbox", 
                "--disable-setuid-sandbox", 
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled"
            ]
        )
        
        # Set a realistic user agent
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # --- THE TOKEN SNIFFER ---
        def handle_response(response):
            nonlocal captured_token
            # Monitor Discord API calls for the registration or login token
            if "api/v9/auth/register" in response.url or "api/v9/users/@me" in response.url:
                if response.status == 200:
                    try:
                        data = response.json()
                        if "token" in data:
                            captured_token = data["token"]
                    except:
                        pass
        
        page.on("response", handle_response)
        # -------------------------

        try:
            # 1. Navigate to Discord/Target
            page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(5000) # Wait for elements to settle

            # 2. Check for reCAPTCHA iframe
            captcha_frame = page.frame_locator("iframe[title*='reCAPTCHA']").first
            if not captcha_frame.locator(".recaptcha-checkbox-border").is_visible():
                return {"status": "error", "message": "CAPTCHA iframe not visible. Check Render IP logs."}

            # 3. Solve the Audio Challenge
            captcha_frame.locator(".recaptcha-checkbox-border").click()
            page.wait_for_timeout(3000)

            challenge_frame = page.frame_locator("iframe[title*='challenge']").first
            challenge_frame.locator("#recaptcha-audio-button").click()
            page.wait_for_timeout(2000)

            audio_url = challenge_frame.locator("#audio-source").get_attribute("src")
            
            # Download and Process Audio
            with httpx.Client() as client:
                resp = client.get(audio_url)
                with open(mp3_path, "wb") as f:
                    f.write(resp.content)
            
            audio = AudioSegment.from_mp3(mp3_path)
            audio.export(wav_path, format="wav")

            # Speech to Text
            recognizer = sr.Recognizer()
            with sr.AudioFile(wav_path) as source:
                audio_data = recognizer.record(source)
                solution = recognizer.recognize_google(audio_data)

            # 4. Input Solution
            challenge_frame.locator("#audio-response").fill(solution)
            challenge_frame.locator("#recaptcha-verify-button").click()
            page.wait_for_timeout(3000)

            return {
                "status": "success", 
                "solution": solution,
                "token": captured_token, # This is the "Cookie"
                "url": target_url
            }

        except Exception as e:
            return {"status": "error", "message": str(e)}
        
        finally:
            browser.close()
            for f in [mp3_path, wav_path]:
                if os.path.exists(f): os.remove(f)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)
