#!/usr/bin/env python3
"""Простой сервер с прокси для тестирования гибридного подхода TIPO-STO"""

from http.server import HTTPServer, SimpleHTTPRequestHandler
import urllib.request
import urllib.error
import json
import base64
import ssl

# Настройки Rent1C (публичный URL)
RENT1C_ODATA = "https://aclient.1c-hosting.com/1R96614/1R96614_AA61AS_e771ys34or/odata/standard.odata"
RENT1C_WEB = "https://aclient.1c-hosting.com/1R96614/1R96614_AA61AS_e771ys34or"
RENT1C_USER = "Администратор"
RENT1C_PASS = ""  # Пустой пароль

# Отключаем проверку SSL для тестов
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

class ProxyHandler(SimpleHTTPRequestHandler):

    def do_POST(self):
        if self.path.startswith('/proxy/odata/'):
            self.proxy_odata_post()
        else:
            self.send_error(404, "Not Found")

    def proxy_odata_post(self):
        """Проксирование POST запросов к OData"""
        odata_path = self.path.replace('/proxy/odata/', '')
        url = f"{RENT1C_ODATA}/{odata_path}"

        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)

            credentials = base64.b64encode(f"{RENT1C_USER}:{RENT1C_PASS}".encode()).decode()

            req = urllib.request.Request(url, data=body, method='POST')
            req.add_header('Authorization', f'Basic {credentials}')
            req.add_header('Content-Type', 'application/json')
            req.add_header('Accept', 'application/json')

            with urllib.request.urlopen(req, timeout=30, context=ssl_context) as response:
                data = response.read()

                self.send_response(201)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(data)

        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8', errors='ignore')
            self.send_response(e.code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"HTTP {e.code}: {error_body}"}).encode())
        except Exception as e:
            self.send_error_json(500, str(e))

    def do_OPTIONS(self):
        """Handle CORS preflight"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        if self.path.startswith('/proxy/odata/'):
            self.proxy_odata()
        elif self.path == '/proxy/webclient':
            self.proxy_webclient()
        elif self.path == '/proxy/config':
            self.send_config()
        else:
            super().do_GET()

    def proxy_odata(self):
        """Проксирование OData запросов к Rent1C"""
        odata_path = self.path.replace('/proxy/odata/', '')
        url = f"{RENT1C_ODATA}/{odata_path}"

        try:
            credentials = base64.b64encode(f"{RENT1C_USER}:{RENT1C_PASS}".encode()).decode()

            req = urllib.request.Request(url)
            req.add_header('Authorization', f'Basic {credentials}')
            req.add_header('Accept', 'application/json')

            with urllib.request.urlopen(req, timeout=30, context=ssl_context) as response:
                data = response.read()

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(data)

        except urllib.error.HTTPError as e:
            self.send_error_json(e.code, f"HTTP Error: {e.reason}")
        except urllib.error.URLError as e:
            self.send_error_json(503, f"Connection Error: {e.reason}")
        except Exception as e:
            self.send_error_json(500, str(e))

    def proxy_webclient(self):
        """Проверка доступности веб-клиента"""
        url = f"{RENT1C_WEB}/ru_RU/"

        try:
            credentials = base64.b64encode(f"{RENT1C_USER}:{RENT1C_PASS}".encode()).decode()

            req = urllib.request.Request(url)
            req.add_header('Authorization', f'Basic {credentials}')

            with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "ok",
                    "code": response.status,
                    "url": url
                }).encode())

        except Exception as e:
            self.send_error_json(503, str(e))

    def send_config(self):
        """Отдать конфигурацию для клиента"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({
            "web_url": RENT1C_WEB
        }).encode())

    def send_error_json(self, code, message):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode())

    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {args[0]}")

if __name__ == '__main__':
    port = 8765
    print(f"🚀 TIPO-STO Test Server")
    print(f"📡 OData: {RENT1C_ODATA}")
    print(f"🌐 Web: {RENT1C_WEB}")
    print(f"🔗 Открой: http://localhost:{port}/test_hybrid_proxy.html")
    print(f"⏹  Ctrl+C для остановки\n")

    server = HTTPServer(('', port), ProxyHandler)
    server.serve_forever()
