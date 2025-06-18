import scraper
import json

# --- Test Configuration ---
TARGET_URL = 'https://shreycation.substack.com'
# --------------------------

def run_test():
    """Runs the scraper directly and processes the output."""
    print(f"Starting direct scraper test for URL: {TARGET_URL}")
    
    collected_items = []
    
    try:
        # We are calling the generator function from the scraper directly
        for message in scraper.run_scraper(sources=[TARGET_URL]):
            if message and message.startswith('___JSON_ITEM___'):
                payload = message[15:]
                if payload:
                    try:
                        item = json.loads(payload)
                        print(f"[ITEM] Collected item: {item.get('title')}")
                        collected_items.append(item)
                    except json.JSONDecodeError:
                        print(f"[ERROR] Failed to decode item JSON: {payload}")
            elif message:
                print(f"[LOG] {message}")
        
        print("\\n--- SCRAPE COMPLETE ---")
        print(f"Successfully collected {len(collected_items)} items.")
        
        if collected_items:
            final_json = {
                "team_id": "aline123_test",
                "items": collected_items
            }
            with open('test_output.json', 'w', encoding='utf-8') as f:
                json.dump(final_json, f, ensure_ascii=False, indent=2)
            print("Wrote results to test_output.json")

    except Exception as e:
        print(f"An unexpected error occurred during the test: {e}")

if __name__ == '__main__':
    run_test() 