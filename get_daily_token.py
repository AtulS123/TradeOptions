import os
import webbrowser
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
from kiteconnect import KiteConnect
from dotenv import load_dotenv

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load Environment Variables
load_dotenv()

# Configuration
# Fallback to values observed in test_connection.py if not in .env
API_KEY = os.getenv("API_KEY", "5f814cggb2e7m8z9")
API_SECRET = os.getenv("API_SECRET", "l7tc02thzpmeack5ge4xbwl3dboalz4m")
PORT = 5000
REDIRECT_URI = f"http://127.0.0.1:{PORT}/callback"

# Global to store the token
captured_request_token = None

class TokenHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global captured_request_token
        
        # Parse URL
        parsed_path = urlparse(self.path)
        
        # Check if path aligns if necessary, but generally we just want the token
        # if parsed_path.path != "/callback": ... (Strict mode optional)
        
        query_params = parse_qs(parsed_path.query)
        
        if "request_token" in query_params:
            captured_request_token = query_params["request_token"][0]
            
            # Send Success Response to Browser
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            html_content = """
            <html>
                <head>
                    <title>Login Successful</title>
                    <style>
                        body { font-family: 'Segoe UI', sans-serif; text-align: center; padding-top: 50px; background-color: #f0f2f5; }
                        .container { background: white; padding: 40px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); display: inline-block; }
                        h1 { color: #2ecc71; }
                        p { color: #555; }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h1>Login Successful!</h1>
                        <p>Request Token captured.</p>
                        <p>You can close this window and return to the application.</p>
                    </div>
                    <script>window.open('', '_self', ''); window.close();</script>
                </body>
            </html>
            """
            self.wfile.write(html_content.encode('utf-8'))
            
            # We got the token, let's stop the server
            # We can't stop directly in the handler thread easily without a flag,
            # but we can assume the main loop checks `captured_request_token`
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Missing request_token parameter.")

    def log_message(self, format, *args):
        # Silence default server logs
        return

def get_access_token():
    global captured_request_token
    
    kite = KiteConnect(api_key=API_KEY)
    
    login_url = kite.login_url()
    # Ensure standard usage of redirect_uri if needed, 
    # but usually Kite app settings determine the redirect.
    # We'll assume the user has set http://127.0.0.1:8000 as a redirect URI in Zerodha Console.
    # If not, this automated flow waits for the user to manually paste the token or configure the URI.
    
    logger.info("Initializing Login Flow...")
    logger.info(f"Attempting to open Browser with URL: {login_url}")
    print("\n" + "="*60)
    print("ACTION REQUIRED: Please login to Zerodha in your browser.")
    print(f"If the browser did not open, copy and paste this URL:\n{login_url}")
    print("="*60 + "\n")
    
    try:
        webbrowser.open(login_url)
    except Exception as e:
        logger.error(f"Failed to launch browser automatically: {e}")
    
    server_address = ('127.0.0.1', PORT)
    httpd = HTTPServer(server_address, TokenHandler)
    
    logger.info(f"Listening for callback on port {PORT}...")
    logger.info(f"NOTE: Ensure your Kite App Redirect URI is set to: {REDIRECT_URI}")
    
    # Non-blocking server loop attempt or just handle_request loop
    while captured_request_token is None:
        httpd.handle_request()
        
    logger.info("Token Captured!")
    
    # Exchange Token
    logger.info("Generating Access Token...")
    try:
        data = kite.generate_session(captured_request_token, api_secret=API_SECRET)
        access_token = data["access_token"]
        
        logger.info(f"Success! Access Token: {access_token[:6]}...{access_token[-4:]}")
        
        # Save to file
        with open("access_token.txt", "w") as f:
            f.write(access_token)
        logger.info("Saved to access_token.txt")
        
        # update .env slightly harder to do safely with parsing, but file is sufficient for main.py fallback
        # Let's just output success
        
    except Exception as e:
        logger.error(f"Failed to generate session: {e}")

if __name__ == "__main__":
    get_access_token()
