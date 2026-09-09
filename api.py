from functools import wraps
import time, random,base64
from flask import Flask, jsonify, request
print(__name__)

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False
# In-memory storage: { "client_ip": [request_count, window_start_timestamp] }
CACHE_NUMBERS = set()
RATE_LIMIT_STORE = {}


def generate_random_user():
    # Custom logic or conditional values
    number = random.randint(100000,4500000)
    while number in CACHE_NUMBERS:
        number = random.randint(100000,4500000)
    CACHE_NUMBERS.add(number)
    return {
        "id": number,
        "name": f"user_{number}",
    }
MOCK_DATA = [generate_random_user() for i in range(1, 300)]
def decode_cursor(cursor_str):
    #Decodes a base64 string to get the starting numeric offset.
    if not cursor_str:
        return 0
    try:
        return int(base64.b64decode(cursor_str.encode()).decode())
    except Exception:
        return 0


def encode_cursor(offset):
    #Encodes a numeric offset into a base64 cursor string.
    return base64.b64encode(str(offset).encode()).decode()
def rate_limit(requests_limit=5, window_seconds=60):
    def decorator(f):
        
        @wraps(f)
        def wrapped(*args, **kwargs):
            # Extracts the IP best not to use in production for this can be spoofed.
            
            client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
            if client_ip and "," in client_ip:
                client_ip = client_ip.split(",")[0].strip()
                
                
            now = int(time.time())
            
            request_count, window_start = RATE_LIMIT_STORE.get(client_ip, [0,now])
            
            if now - window_start > window_seconds:
                request_count = 0 
                window_start = now
            if request_count >= requests_limit:
                retry_after = int(window_seconds - (now - window_start))
                
                response = jsonify({
                    "error": "Too Many Requests",
                    "message": f"Rate Limit exceeded. Try again in {retry_after} seconds."
                })
                response.status_code = 429
                response.headers["Retry-after"] = str(retry_after)
                response.headers["X-RateLimit-Limit"] = str(requests_limit)
                response.headers["X-RateLimit-Remaining"] = "0"
                return response
            
            RATE_LIMIT_STORE[client_ip] = [request_count+1, window_start]
            
            response = app.make_response(f(*args, **kwargs))
            
            response.headers["X-RateLimit-Limit"] = str(requests_limit)
            response.headers["X-RateLimit-Remaining"] = str(int(requests_limit - (request_count+1)))
            response.headers["X-RateLimit-Reset"] = str(int(window_start+window_seconds))
            
            return response
        
        return wrapped
    return decorator
# @app.route("/data")
# @rate_limit(requests_limit=5, window_seconds=60)
# def hello():
#     return jsonify({"status": "success", "data": "Protected endpoint response"}) 
@app.route("/v1/users/<int:user_id>/<endpoint>", methods=["GET"])
@rate_limit(requests_limit=10, window_seconds=15)
def get_paginated_data(user_id, endpoint):
    # Retrieve query parameters with defaults
    limit = min(int(request.args.get("limit", 10)), 10)  # Cap max limit to 10
    cursor = request.args.get("cursor", "")
    # Determine pagination slice
    start_index = decode_cursor(cursor)
    print(start_index)
    data = MOCK_DATA 
    #if sort_order == "Asc" else list(reversed(MOCK_DATA))
    paginated_slice = data[start_index : start_index + limit]
    print(paginated_slice)

    # Build next cursor if more data exists
    next_index = start_index + len(paginated_slice)
    next_cursor = encode_cursor(next_index) if next_index < len(data) else None

    # Return cursor pagination JSON response schema
    return (
        jsonify(
            {
                "previousPageCursor": (
                    encode_cursor(max(0, start_index - limit))
                    if start_index > 0
                    else None
                ),
                "nextPageCursor": next_cursor,
                "data": paginated_slice,
            }
        ),
        200,
    )
@app.route("/")
def home():
    return "http://127.0.0.1:5000/v1/users/1/followers?cursor="
if __name__ == '__main__':
    app.run(
        debug=True,
        threaded=True
        )