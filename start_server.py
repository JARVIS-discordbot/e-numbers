
#!/usr/bin/env python3
"""
Simple script to start the Flask API server on port 5000
"""
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api import app

if __name__ == '__main__':
    print("Starting E-Numbers API server...")
    print("Server will be available at http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)
# change debug=False to true for debug mode
