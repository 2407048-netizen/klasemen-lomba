import sys
import os

# Tambahkan parent folder ke path agar bisa import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from werkzeug.middleware.proxy_fix import ProxyFix

# Fix untuk Vercel proxy
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# Handler untuk Vercel
def handler(request):
    return app(request.environ, lambda *args: None)