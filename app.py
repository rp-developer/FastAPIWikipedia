from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from urllib.parse import quote_plus
import redis.asyncio as aioredis
from typing import Optional
import httpx
import json
import os
app = FastAPI()

redis_host = os.environ.get("DATABASE_URL", "redis://localhost:6379")
redis_client = aioredis.from_url(redis_host)

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    data = {
        "page": "Home page"
    }
    return templates.TemplateResponse("index.html", {"request": request, "data": data})


@app.get("/submit", response_class=HTMLResponse)
async def page(request: Request, query: Optional[str] = Query(None)):
    if query == None:
        error = "No query parameters detected"
        return templates.TemplateResponse("404.html", {
            "error": error,
            "request": request
        }, status_code=400)
    
    query = query.replace(" ", "_").title()
    
    encodedQuery = quote_plus(query)
    redis_data = await redis_client.get(encodedQuery)
    print(redis_data)
    if redis_data:
        cached_data = json.loads(redis_data)
        return templates.TemplateResponse("summary.html", {
            "request": request, 
            "page": cached_data['page'], 
            "summary": cached_data['summary'], 
            "title": cached_data['title']
            })
    
    else:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{(query)}", follow_redirects=True)
            print(response.status_code)
            if response.status_code == 404:
                error = "Page not found"
                return templates.TemplateResponse("404.html", {
                    "error": error,
                    "request": request
                })
            responseData = response.json()
            summary = responseData['extract']
            page = responseData['content_urls']['desktop']['page']
            title = responseData['title']

            redisSetData = {
                'page': page, 
                'title':title, 
                'summary':summary}

            await redis_client.setex(encodedQuery, 3600, json.dumps(redisSetData)) 

            return templates.TemplateResponse("summary.html", {"request": request, "page": page, "summary": summary, "title": title})
@app.get('/submit/api')
async def api(request: Request, query: Optional[str] = Query(None)):
    if query is None:
        error = {"error": "No query parameters detected"}
        raise HTTPException(
            status_code=400,
            detail=error
        )
    query = query.replace(" ", "_").title()

    encodedQuery = quote_plus(query)
    redis_data = await redis_client.get(encodedQuery)
    print(redis_data)
    if redis_data:
        cached_data = json.loads(redis_data)
        return {
            "page": cached_data['page'], 
            "summary": cached_data['summary'], 
            "title": cached_data['title'],
            }
    
    else:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{(query)}", follow_redirects=True)
            print(response.status_code)
            if response.status_code == 404:
                error = "Page not found"
                return {
                    "error": error,
                }
            responseData = response.json()
            if 'extract' in responseData and 'content_urls' in responseData:
                summary = responseData['extract']
                page = responseData['content_urls']['desktop']['page']
                title = responseData['title']
            

            redisSetData = {
                'page': page, 
                'title':title, 
                'summary':summary}

            await redis_client.setex(encodedQuery, 3600, json.dumps(redisSetData)) 

            return {"page": page, "summary": summary, "title": title}