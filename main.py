import os
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security.api_key import APIKeyHeader
from playwright.sync_api import sync_playwright
import speech_recognition as sr
from pydub import AudioSegment
import httpx

app = FastAPI()
API_KEY = "consulsofnato"
api_key_header = APIKeyHeader(name="access_token", auto_error=False)

def verify_key(key: str = Depends(api_key_header)):
    if key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return key

@app.post("/solve_on_page")
def solve_on_page(target_url: str, key: str = Depends(verify_key)):
    with sync_playwright() as p:
        # Launching with specific flags to save RAM
        browser = p.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
        context = browser.new_context()
        page = context.new_page()
        
        try:
            page.goto(target_url)
            
            # 1. Handle reCAPTCHA Checkbox
            captcha_frame = page.frame_locator("iframe[title*='reCAPTCHA']")
            captcha_frame.locator(".recaptcha-checkbox-border").click()
            page.wait_for_timeout(2000)

            # 2. Switch to Audio Challenge
            challenge_frame = page.frame_locator("iframe[title*='recaptcha challenge']")
            challenge_frame.locator("#recaptcha-audio-button").click()
            page.wait_for_timeout(2000)

            # 3. Get Audio URL & Solve
            audio_url = challenge_frame.locator("#audio-source").get_attribute("src")
            
            # Download & Process Audio
            with httpx.Client() as client:
                resp = client.get(audio_url)
                with open("temp.mp3", "wb") as f:
                    f.write(resp.content)
            
            AudioSegment.from_mp3("temp.mp3").export("temp.wav", format="wav")
            
            recognizer = sr.Recognizer()
            with sr.AudioFile("temp.wav") as source:
                audio_data = recognizer.record(source)
                solution = recognizer.recognize_google(audio_data)

            # 4. Input Solution
            challenge_frame.locator("#audio-response").fill(solution)
            challenge_frame.locator("#recaptcha-verify-button").click()
            page.wait_for_timeout(1000)

            return {"status": "success", "solution": solution}

        except Exception as e:
            return {"status": "error", "message": str(e)}
        finally:
            browser.close()
            
