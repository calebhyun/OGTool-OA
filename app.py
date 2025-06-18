from gevent import monkey
monkey.patch_all()

from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import json
import os
import scraper
import time
import uuid
import logging

# Silence noisy loggers
logging.getLogger('trafilatura').setLevel(logging.CRITICAL)
logging.getLogger('webdriver_manager').setLevel(logging.CRITICAL)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!' # Required for SocketIO
# Wrap the app with SocketIO
socketio = SocketIO(app, async_mode='gevent')

UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@app.route('/')
def index():
    return render_template('index.html')

# PDF upload remains a standard HTTP endpoint
@app.route('/scrape_pdf', methods=['POST'])
def scrape_pdf_endpoint():
    pdf_file = request.files.get('pdf_file')
    if pdf_file and pdf_file.filename.lower().endswith('.pdf'):
        # Append .pdf to the UUID filename to preserve the extension
        filename = str(uuid.uuid4()) + ".pdf"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        pdf_file.save(filepath)
        return {'pdf_id': filename}
    return {'error': 'No PDF file found or file is not a PDF'}, 400

def run_scraper_in_background(sid, sources, use_selenium):
    """A wrapper to run the scraper and emit messages over WebSocket."""
    with app.app_context():
        try:
            for message in scraper.run_scraper(sources, use_selenium=use_selenium):
                if message and message.startswith('___JSON_ITEM___'):
                    payload = message[15:]
                    if payload:
                        try:
                            json_data = json.loads(payload)
                            socketio.emit('json_item', json_data, to=sid)
                        except json.JSONDecodeError:
                            socketio.emit('log_message', {'data': f"FATAL: Server failed to decode item data."}, to=sid)
                elif message:
                    socketio.emit('log_message', {'data': message}, to=sid)
            
            socketio.emit('scrape_complete', {'data': 'Scraping process finished.'}, to=sid)

        except Exception as e:
            app.logger.error(f"An error occurred in background task: {e}", exc_info=True)
            socketio.emit('log_message', {'data': f"FATAL: A server error occurred in the background task: {e}"}, to=sid)

@socketio.on('scrape_request')
def handle_scrape_request(data):
    """Handles the scraping request, starting a background task."""
    sid = request.sid
    urls = data.get('urls', '').split()
    pdf_id = data.get('pdf_id')
    use_selenium = data.get('use_selenium', True)
    
    sources = []
    if urls:
        sources.extend(urls)
    
    if pdf_id:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], pdf_id)
        if os.path.exists(filepath):
            sources.append(filepath)

    socketio.start_background_task(
        run_scraper_in_background, 
        sid=sid, 
        sources=sources, 
        use_selenium=use_selenium
    )

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    # Use socketio.run to start a gevent-based server
    socketio.run(app, host='0.0.0.0', port=port) 