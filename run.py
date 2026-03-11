#!/usr/bin/env python
import os
from app import create_app

if __name__ == '__main__':
    app = create_app(os.getenv('FLASK_ENV', 'development'))
    port = int(os.getenv('FLASK_PORT', 5001))
    app.run(host='127.0.0.1', port=port, debug=True)
