import socketio
import sys
import time
import json

# --- Test Configuration ---
TARGET_URL = 'https://shreycation.substack.com'
# --------------------------

sio = socketio.Client()
collected_items = []

@sio.event
def connect():
    print('Connection established. Sending scrape request...')
    sio.emit('scrape_request', {'urls': TARGET_URL})

@sio.event
def log_message(data):
    print(f"[LOG] {data['data']}")
    time.sleep(0.01)

@sio.event
def json_item(item):
    print(f"[ITEM] Found article: {item.get('title')}")
    collected_items.append(item)
    time.sleep(0.01)

@sio.event
def connect_error(data):
    print("The connection failed!")

@sio.event
def disconnect():
    print('Disconnected from server.')
    print('\\n--- SCRAPE COMPLETE ---')
    print(f"Successfully collected {len(collected_items)} items.")
    
    # Optionally, write to a local file for verification
    if collected_items:
        final_json = {
            "team_id": "aline123_test",
            "items": collected_items
        }
        with open('test_output.json', 'w', encoding='utf-8') as f:
            json.dump(final_json, f, ensure_ascii=False, indent=2)
        print("Wrote results to test_output.json")

if __name__ == '__main__':
    try:
        sio.connect('http://127.0.0.1:5000')
        sio.wait()
    except Exception as e:
        print(f"An error occurred: {e}")
        print("Please ensure the main 'app.py' server is running.") 