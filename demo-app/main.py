from fastapi import FastAPI, HTTPException
import psycopg2
import httpx
import os

app = FastAPI()

DB_URL = os.getenv("DATABASE_URL", "postgresql://devuser:devpass@postgres:5432/devdb")
LITELLM_BASE_URL = os.getenv("LITELLM_BASE_URL", "http://localhost:4000")
LITELLM_API_KEY = os.getenv("LITELLM_API_KEY", "sk-my-local-master-key")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/hello")
def hello():
    return {"message": "Hello from inside Docker!"}

@app.get("/db-check")
def db_check():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("SELECT version();")
    version = cur.fetchone()
    conn.close()
    return {"postgres_version": version[0]}

@app.post("/chat")
async def chat(message: dict):
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{LITELLM_BASE_URL}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {LITELLM_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "gemini-flash",
                "messages": [{"role": "user", "content": message["content"]}]
            }
        )
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.text)
        
        data = response.json()
        return {
            "response": data["choices"][0]["message"]["content"],
            "model": data["model"],
            "tokens_used": data["usage"]["total_tokens"]
        }