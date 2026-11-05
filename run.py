"""Локальный запуск JolScan AI без режима отладки."""
import os
from dotenv import load_dotenv
from app import create_app

load_dotenv()
app = create_app()

if __name__ == '__main__':
    from waitress import serve
    port = int(os.getenv('PORT', '5000'))
    print(f'JolScan AI: http://localhost:{port}', flush=True)
    serve(app, host='0.0.0.0', port=port, threads=6)
