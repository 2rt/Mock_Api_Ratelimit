import base64, random
from flask import Flask, jsonify, request

app = Flask(__name__)
app.json.sort_keys = False
# Sample dataset (mimicking a list of user IDs or objects)
#MOCK_DATA = [{"id": i, "username": f"user_{i}"} for i in range(1, 2000)]

def generate_random_user():
    # Custom logic or conditional values
    number = random.randint(100000,4500000)
    
    return {
        "id": number,
        "username": f"user_{number}",
    }
MOCK_DATA = [generate_random_user() for i in range(1, 2000)]
def decode_cursor(cursor_str):
    """Decodes a base64 string to get the starting numeric offset."""
    if not cursor_str:
        return 0
    try:
        return int(base64.b64decode(cursor_str.encode()).decode())
    except Exception:
        return 0


def encode_cursor(offset):
    """Encodes a numeric offset into a base64 cursor string."""
    return base64.b64encode(str(offset).encode()).decode()


@app.route("/v1/users/<int:user_id>/<endpoint>", methods=["GET"])
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

    # Return matching Roblox response schema
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


if __name__ == "__main__":
    app.run(debug=True)