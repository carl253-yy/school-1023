from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import os

PORT = 8000

class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

if __name__ == "__main__":
    os.chdir(os.path.dirname(__file__))
    server = ThreadingHTTPServer(("0.0.0.0", PORT), QuietHandler)
    print(f"Serving on http://localhost:{PORT}")
    server.serve_forever()
