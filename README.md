# LLM Analysis Quiz

A quiz application to test understanding of LLM prompt engineering, API security, and prompt injection vulnerabilities.

## 🚀 Features
- System prompt security testing
- Prompt injection challenge
- API endpoint integration
- Real-time LLM evaluation

## 🛠️ Tech Stack
- **Frontend**: HTML, CSS, JavaScript (hosted on GitHub Pages)
- **Backend**: Python FastAPI (hosted on Render)
- **LLM**: OpenAI-compatible API via AIPIPE

## 📦 Setup

### Prerequisites
- Python 3.11+
- Node.js 20+ (optional, for frontend build)
- AIPIPE token

### Installation
```bash
# Clone repo
git clone https://github.com/YOUR_USERNAMEVidyaRamesh18/llm-analysis-quiz---TDS-P2_Sep-2025.git
cd llm-analysis-quiz

# Install backend dependencies
cd backend
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Edit .env and add your AIPIPE_TOKEN
```

### Running Locally
```bash
# Start backend
cd backend
source .venv/bin/activate
python app.py

# Open frontend (in another terminal)
cd frontend
# Open index.html in browser or use live server
```

## 🚀 Deployment
- **Frontend**: GitHub Pages
- **Backend**: Render

See `docs/deployment.md` for detailed steps.

## 📝 License
MIT License - see LICENSE file

## 👤 Author
Vidya
