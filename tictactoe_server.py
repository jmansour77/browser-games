from http.server import HTTPServer, BaseHTTPRequestHandler

class TicTacToeHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        with open("tictactoe.html", "rb") as f:
            content = f.read()
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format, *args):
        print(f"[TicTacToe] {self.address_string()} - {format % args}")

if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 8080), TicTacToeHandler)
    print("Tic Tac Toe server running at http://localhost:8080")
    server.serve_forever()
