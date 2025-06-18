document.getElementById('scrape-form').addEventListener('submit', function(event) {
    event.preventDefault();

    const logs = document.getElementById('logs');
    const outputContainer = document.getElementById('output-container');
    const downloadLink = document.getElementById('download-link');
    
    logs.innerHTML = '';
    outputContainer.style.display = 'none';

    const urls = document.getElementById('urls').value.trim();
    const pdfFile = document.getElementById('pdf_file').files[0];

    if (!urls && !pdfFile) {
        logs.innerHTML = 'Please enter URLs or select a PDF file.';
        return;
    }

    if (pdfFile && urls) {
        logs.innerHTML = 'Please provide either URLs or a PDF, not both.';
        return;
    }

    logs.innerHTML = 'Connecting to server...<br>';
    const socket = io();

    socket.on('connect', function() {
        logs.innerHTML += 'Connection established. Starting scrape...<br>';
        
        const scrapeParams = {
            urls: urls
        };

        if (pdfFile) {
            // If we have a PDF, we must upload it first to get an ID
            const fileFormData = new FormData();
            fileFormData.append('pdf_file', pdfFile);
            
            fetch('/scrape_pdf', {
                method: 'POST',
                body: fileFormData
            })
            .then(response => response.json())
            .then(data => {
                if (data.pdf_id) {
                    scrapeParams.pdf_id = data.pdf_id;
                    socket.emit('scrape_request', scrapeParams);
                } else {
                    logs.innerHTML += 'Error uploading PDF.<br>';
                    socket.disconnect();
                }
            });
        } else {
            socket.emit('scrape_request', scrapeParams);
        }
    });

    let collectedItems = [];

    socket.on('log_message', function(msg) {
        logs.innerHTML += msg.data + '<br>';
        logs.scrollTop = logs.scrollHeight;
    });

    socket.on('json_item', function(item) {
        collectedItems.push(item);
    });

    socket.on('scrape_complete', function(msg) {
        logs.innerHTML += msg.data + '<br>';
        logs.scrollTop = logs.scrollHeight;

        // Assemble the final JSON and create the download link
        if (collectedItems.length > 0) {
            const finalJson = {
                team_id: "aline123",
                items: collectedItems
            };
            const jsonString = JSON.stringify(finalJson, null, 2);
            
            // Display the JSON
            const jsonOutput = document.getElementById('json-output');
            jsonOutput.textContent = jsonString;

            // Create download link
            const blob = new Blob([jsonString], { type: 'application/json' });
            const url = window.URL.createObjectURL(blob);
            downloadLink.href = url;
            outputContainer.style.display = 'block';
        } else {
            logs.innerHTML += 'No items were found to download.<br>';
        }
        socket.disconnect();
    });

    socket.on('disconnect', function() {
        logs.innerHTML += 'Disconnected from server.<br>';
    });

    socket.on('connect_error', (err) => {
        logs.innerHTML += `Connection failed: ${err.message}. Please check the server and refresh the page.`;
    });
}); 