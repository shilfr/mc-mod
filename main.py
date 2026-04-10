import os
import httpx
import speech_recognition as sr
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security.api_key import APIKeyHeader
from pydub import AudioSegment

app = FastAPI()

# Replace with your own secure key
API_KEY = "YOUR_SECRET_KEY" 
api_key_header = APIKeyHeader(name="access_token", auto_error=False)

def verify_key(key: str = Depends(api_key_header)):
    if key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return key

@app.post("/solve")
async def solve_captcha(audio_url: str, key: str = Depends(verify_key)):
    mp3_path = "temp.mp3"
    wav_path = "temp.wav"
    
    try:
        # 1. Download the audio file
        async with httpx.AsyncClient() as client:
            resp = await client.get(audio_url)
            if resp.status_code != 200:
                return {"status": "error", "message": "Failed to download audio."}
            with open(mp3_path, "wb") as f:
                f.write(resp.content)

        # 2. Convert MP3 to WAV
        audio = AudioSegment.from_mp3(mp3_path)
        audio.export(wav_path, format="wav")

        # 3. Process with Speech Recognition
        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)
            # Google's free speech-to-text API
            result = recognizer.recognize_google(audio_data)
            
        return {"status": "success", "code": result}

    except sr.UnknownValueError:
        return {"status": "error", "message": "Could not understand the audio."}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    
    finally:
        # 4. Cleanup temp files so Render doesn't run out of disk space
        if os.path.exists(mp3_path):
            os.remove(mp3_path)
        if os.path.exists(wav_path):
            os.remove(wav_path)
