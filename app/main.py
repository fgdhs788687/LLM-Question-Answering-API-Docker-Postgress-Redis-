import uvicorn
import asyncio
from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from app.database.deps import DbSession
from fastapi.responses import JSONResponse
from app.api.routes import auth, chat
from app.api.user_deps import CurrentUser

app = FastAPI()


app.include_router(auth.router)
app.include_router(chat.router)

@app.get('/')
async def root():
  return {'status': 'okay'}

# Test endpoint to see if the db is up or not:
@app.get('/health')
async def health(db: DbSession):

  try:
    await db.execute(text('SELECT 1'))
    return {'status':'ok','db':'up'}
  except Exception:
    return JSONResponse(status_code=503, content={'status':'degraded','db':'down'})

if __name__ == "__main__":
  uvicorn.run(
    'app.main:app', host='0.0.0.0', port=8000, reload=True
)
