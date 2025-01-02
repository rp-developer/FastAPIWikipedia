from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from urllib.parse import quote_plus
import redis
import httpx
import json
app = FastAPI()

redis_client = redis.Redis(host='localhost', port=6379, db=0)

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    data = {
        "page": "Home page"
    }
    return templates.TemplateResponse("index.html", {"request": request, "data": data})


@app.get("/submit", response_class=HTMLResponse)
async def page(request: Request, query: str = Query(...)):
    query = query.replace(" ", "_").title()
    encodedQuery = quote_plus(query)
    redis_data = redis_client.get(encodedQuery)
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
            response = await client.get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{(query)}")
            responseData = response.json()
            summary = responseData['extract']
            page = responseData['content_urls']['desktop']['page']
            title = responseData['title']

            redisSetData = {
                'page': page, 
                'title':title, 
                'summary':summary}

            redis_client.setex(encodedQuery, 3600, json.dumps(redisSetData)) 

            return templates.TemplateResponse("summary.html", {"request": request, "page": page, "summary": summary, "title": title})
@app.get('/submit/api')
async def api(request: Request, query: str = Query(...)):
    query = query.replace(" ", "_").title()

    encodedQuery = quote_plus(query)
    redis_data = redis_client.get(encodedQuery)
    print(redis_data)
    if redis_data:
        cached_data = json.loads(redis_data)
        return {
            "page": cached_data['page'], 
            "summary": cached_data['summary'], 
            "title": cached_data['title']
            }
    
    else:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{(query)}")
            responseData = response.json()
            summary = responseData['extract']
            page = responseData['content_urls']['desktop']['page']
            title = responseData['title']

            redisSetData = {
                'page': page, 
                'title':title, 
                'summary':summary}

            redis_client.setex(encodedQuery, 3600, json.dumps(redisSetData)) 

            return {"page": page, "summary": summary, "title": title}