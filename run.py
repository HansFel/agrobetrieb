#!/usr/bin/env python
import os
from dotenv import load_dotenv
from app import create_app

# Lade .env-Datei BEVOR create_app aufgerufen wird
load_dotenv()

if __name__ == '__main__':
    app = create_app(os.getenv('FLASK_ENV', 'development'))
    port = int(os.getenv('FLASK_PORT', 5001))
    app.run(host='127.0.0.1', port=port, debug=True)
