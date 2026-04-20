Project Activation Instructions

To activate the project, you need the following installed:
- Node.js
- Python

---------------------------------------------------------
Frontend
---------------------------------------------------------
cd frontend
npm install
npm run dev

---------------------------------------------------------
Backend
---------------------------------------------------------
cd backend

# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install fastapi
pip install uvicorn
pip install sqlalchemy
# Note: You can also use: pip install -r requirements.txt

# Run the server
uvicorn api_app:app --reload
