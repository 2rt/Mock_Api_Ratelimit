# Follower Scraper

A multithreaded scraper that pulls follower data through a local API server, using a worker pool with automatic rate-limit (429) handling and retry/re-queueing.

## How it works

- A pool of worker threads pulls `(username, userid, cursor)` tasks off a shared queue and requests each page of followers from a local API server at `http://127.0.0.1:5000`.
- Results are written to `output/{username}.txt`, one name per line, guarded by a lock so multiple workers can write safely without clobbering each other.
- If a worker gets a `429` response, it re-queues the task and clears a shared `pause_event`, which pauses every worker thread at once.
- A separate manager thread watches for that pause signal, sleeps for a cooldown period, then resumes all workers by setting the event again.
- Pagination is handled automatically — if the API response includes a `nextPageCursor`, a new task is queued for the next page.
- If the local server goes down mid-run (connection error), the scraper stops all workers gracefully and re-queues the task that was in flight.

## Requirements

- Python 3
- `requests`
- `Flask`
- A local API server (`api.py`) running on port 5000, exposing:
  ```
  GET /v1/users/{userid}/followers?cursor={cursor}
  ```
  returning JSON in the form:
  ```json
  {
    "data": [{ "name": "..." }, ...],
    "nextPageCursor": "..." // optional, omitted on the last page
  }
  ```

## Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
2. Start the local server first:
   ```
   python api.py
   ```
3. Run the scraper:
   ```
   python scraper.py
   ```
   If the server isn't up yet, `scraper.py` will prompt you to start it and wait until it comes online before continuing.

## Configuration

Set these in `main()`:

| Variable | Description |
|---|---|
| `thread_count` | Number of worker threads (default 5) |
| `cooldown` | Seconds to pause all workers after hitting a 429 (default 5) |
| `targets` | List of `(username, userid, starting_cursor)` tuples to scrape |

## Output

- Per-user text files in `output/`, e.g. `output/user_1.txt`
- A summary printed at the end showing total items scraped per user

## Notes

- Workers keep running until the queue is empty or `stop_event` is set (e.g. on a connection failure to the local server).
- The manager thread is a daemon thread — it exits automatically once the main thread finishes, so it doesn't need to be joined.
