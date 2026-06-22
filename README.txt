Project Activation Instructions

To activate the project, you need the following installed:
- Node.js
- Python


---------------------------------------------------------
Backend
---------------------------------------------------------
OPEN CMD
git clone -b fixed_version_11th_june --single-branch https://github.com/isarmatan/AutonomousParkingLotSimulator.git 
cd AutonomousParkingLotSimulator\backend
python -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
uvicorn api_app:app --reload


---------------------------------------------------------
Frontend
---------------------------------------------------------
OPEN CMD
cd AutonomousParkingLotSimulator\frontend
npm install
npm run dev



LaCAM0 Troubleshooting
---------------------------------------------------------
If LaCAM0 fails with:

lacam0 exe not found

make sure this file exists:

lacam0\build\main.exe

If it is missing, compile LaCAM0:

1. Install Visual Studio Build Tools.
2. Select "Desktop development with C++".
3. Install CMake.
4. Open "Developer Command Prompt for Visual Studio".
5. Run:

cd AutonomousParkingLotSimulator\lacam0
cmake -S . -B build
cmake --build build --config Release

If the executable is created here:

lacam0\build\Release\main.exe

copy it to the expected location:

copy build\Release\main.exe build\main.exe

Restart the backend after the file is created.
