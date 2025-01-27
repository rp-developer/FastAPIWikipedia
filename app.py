from fastapi import FastAPI, Request, Query, HTTPException, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from urllib.parse import quote_plus
import redis.asyncio as aioredis
from typing import Optional
import httpx
import json
import os

from symspellpy import SymSpell, Verbosity
app = FastAPI()
sym_spell = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)

# Load a frequency dictionary
dictionary_path = "frequency_dictionary_en_82_765.txt"
sym_spell.load_dictionary(dictionary_path, term_index=0, count_index=1)

# Autocorrect using SymSpell
def autocorrect(query: str) -> str:
    suggestions = sym_spell.lookup_compound(query, max_edit_distance=2)
    return suggestions[0].term if suggestions else query

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
redis_client = aioredis.from_url(redis_url)

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    data = {
        "page": "Home page"
    }
    return templates.TemplateResponse("index.html", {"request": request, "data": data})


@app.get("/submit", response_class=HTMLResponse)
async def page(request: Request, query: str):
    if query == None:
        error = "No query parameters detected"
        return templates.TemplateResponse("404.html", {
            "error": error,
            "request": request
        }, status_code=400)
    if query == "":
        error = "No search detected"
        return templates.TemplateResponse("404.html", {
            "error": error,
            "request": request
        })
    encodedQuery = quote_plus(query.lower().replace(" ", "_").title())
    redis_data = await redis_client.get(encodedQuery)
    if redis_data:
        cached_data = json.loads(redis_data)
        return templates.TemplateResponse("summary.html", {
            "request": request, 
            "page": cached_data['page'], 
            "summary": cached_data['summary'], 
            "title": cached_data['title']
            })
    if not redis_data:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{(query)}", follow_redirects=True)
            print(response.status_code)
            if response.status_code == 404:
                queryAutoCorrect = str(autocorrect(query))
                encodedAutoCorrectQuery = quote_plus(queryAutoCorrect.lower().replace(" ", "_").title())
                print(encodedAutoCorrectQuery)
                responseAutoCorrect = await client.get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{(encodedAutoCorrectQuery)}", follow_redirects=True)
                if responseAutoCorrect.status_code == 404:
                    error = "Page not found. Check for a typo in your search"
                    return templates.TemplateResponse("404.html", {
                        "error": error,
                        "request": request
                    })
                response = responseAutoCorrect
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
async def api(query: Optional[str] = Query(None)):
    if query is None:
        error = {"error": "No query parameters detected"}
        raise HTTPException(
            status_code=400,
            detail=error
        )
    encodedQuery = quote_plus(query.lower().replace(" ", "_").title())
    redis_data = await redis_client.get(encodedQuery)
    print(redis_data)
    if redis_data:
        cached_data = json.loads(redis_data)
        return {
            "page": cached_data['page'], 
            "summary": cached_data['summary'], 
            "title": cached_data['title'],
            }
    
    if not redis_data:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{(query)}", follow_redirects=True)
            if response.status_code == 404:
                queryAutoCorrect = str(autocorrect(query))
                encodedAutoCorrectQuery = quote_plus(queryAutoCorrect.lower().replace(" ", "_").title())
                print(encodedAutoCorrectQuery)
                responseAutoCorrect = await client.get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{(encodedAutoCorrectQuery)}", follow_redirects=True)
                if responseAutoCorrect.status_code == 404:
                    error = "Page not found. Check for a typo in your query"
                    return {
                        "error": error,
                    }
                response = responseAutoCorrect
            if not response.status_code == 404:
                responseData = response.json()
                summary = responseData['extract']
                page = responseData['content_urls']['desktop']['page']
                title = responseData['title']
                

                redisSetData = {
                    'page': page, 
                    'title':title, 
                    'summary':summary}

                await redis_client.setex(encodedQuery, 3600, json.dumps(redisSetData)) 

                return {"page": page, "summary": summary, "title": title}