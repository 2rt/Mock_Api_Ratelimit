import time, requests, os
from queue import Empty, Queue
from threading import Event, Lock, Thread

stop_event = Event()
pause_event = Event()
pause_event.set()
file_lock = Lock()
rate_limit_lock = Lock()
debounce = False
def server_not_running(worker_id: int):
    print(
                f"\n[Worker {worker_id}] ERROR: Local Server at Port 5000 is not running! Please start the server and try again."
            )

def worker_thread(worker_id: int, task_queue: Queue, results_tracker: dict):
    session = requests.Session()

    while not stop_event.is_set():
        #Due to how fast modern computers are, we need to pause the threads when a 429 is hit, this will prevent the threads from hammering the server and getting more 429s.
        pause_event.wait()

        try:
            #Stored as a tuple for there is no duplicates, eliminates the possibility of race conditions.
            username, userid, cursor = task_queue.get(timeout=1)
        except Empty:
            break

        try:
            if not pause_event.is_set():
                task_queue.put((username, userid, cursor))
                task_queue.task_done()
                continue
            response = session.get(f"http://127.0.0.1:5000/v1/users/{userid}/followers?cursor={cursor}", timeout=5)
            if response.status_code == 429:
                #print(f"[Worker {worker_id}] Hit 429! Re-queueing task {username} (cursor: '{cursor}')! Re-queueing")
                task_queue.put((username,userid,cursor))
                task_queue.task_done()
                if rate_limit_lock.acquire(blocking=False):
                    try:
                        if pause_event.is_set():
                            #print(f"[Worker {worker_id}] Hit 429! Immediately pausing all workers...")
                            print(f"[Worker {worker_id}] Hit 429! Re-queueing task {username} (cursor: '{cursor}')! Re-queueing")
                            pause_event.clear()
                    finally:
                        rate_limit_lock.release()
                continue

            if response.status_code == 200:
                data = response.json()
                items = [f"{x['name']}\n"for x in data.get("data", [])]
                os.makedirs("output", exist_ok=True)
                with file_lock:
                    with open(f"output/{username}.txt", "a") as f:
                        f.writelines(items)
            results_tracker[username] = (
                results_tracker.get(username, 0) + len(items)
                
            )
            print(
                f"[Worker {worker_id}] Saved {len(items)} items for {username}, cursor: {cursor}"
            )
            next_cursor = data.get("nextPageCursor")
            if next_cursor:
                task_queue.put((username,userid,next_cursor))
            task_queue.task_done()
        except requests.exceptions.ConnectionError:
            print(
                    f"\n[Worker {worker_id}] ERROR: Local Server at Port 5000 is not running! Please start the server and try again."
                )
            stop_event.set()
            task_queue.put((username, userid, cursor))
            task_queue.task_done()
        except requests.exceptions.Timeout:
            print(
                f"[Worker {worker_id}] Request timed out for {username}. Re-queueing"
            )
            task_queue.put((username,userid,cursor))
            task_queue.task_done()
        except Exception as err:
            print(f"[Worker {worker_id}] Error processing {username}: {err}")
            # Re-queue task on connection error
            task_queue.put((username, userid, cursor))
            task_queue.task_done()
                
        


def manager_thread(task_queue: Queue, cooldown_seconds: int = 20):
    print("[Manager] Thread active. Monitoring workers...")

    while not stop_event.is_set():
        if not pause_event.is_set():
            print(
                f"[Manager] 429 Rate limit caught! Pausing workers"
            )
            time.sleep(cooldown_seconds)
            print(
                "[Manager] Cooldown finished. Resuming worker threads"
            )
            pause_event.set()

        time.sleep(0.5)
    print("[Manager] Finished monitoring.")


def is_server_online(url="http://127.0.0.1:5000"):
    try:
        requests.get(url,timeout=5)
        return True
    except requests.exceptions.ConnectionError:
        return False
    
def main():
    if not is_server_online():
        input(
            "Error: Local server at Port 5000, not running run api.py, Let it setup then hit enter\n"
        )
        while not is_server_online():
            input()
        print("Server Started Thank you.")
    thread_count = 5
    cooldown = 20 #  Cooldown for the 429 in seconds.
    targets = [
        ("user_1", "1", ""),
        #("user_2", "2", "")
    ]
    task_queue = Queue()
    for target in targets:
        task_queue.put(target)
    results_tracker = {}
    workers = []

    for i in range(thread_count):
        worker = Thread(
            target = worker_thread,
            args = (i + 1, task_queue, results_tracker),
            name=f"Worker-{i+1}"
        )
        
        worker.start()
        workers.append(worker)
        
    Manager = Thread(
        target = manager_thread,
        args = (task_queue, cooldown),
        daemon=True
    )
    Manager.start()
    for worker in workers:
        worker.join()
    print("\n --- RESULTS ---")
    for user, total in results_tracker.items():
        print(f"{user}: {total} items scraped")

if __name__ == "__main__":
    main()