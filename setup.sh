#!/bin/bash
# Quick start script for Multimodal RAG

echo "🚀 Multimodal RAG - Quick Start"
echo "==============================="
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Check for .env file
if [ ! -f ".env" ]; then
    echo ""
    echo "⚠️  No .env file found!"
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo ""
    echo "⚠️  Please edit .env and add your API keys:"
    echo "   - OPENAI_API_KEY"
    echo "   - GOOGLE_API_KEY"
    echo "   - UPSTAGE_API_KEY (optional)"
    echo ""
    echo "After adding your keys, run this script again."
    exit 1
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Place your PDF files in: data/raw/"
echo "2. Process a PDF: cd src && python main.py process ../data/raw/your_file.pdf"
echo "3. Query: python main.py query 'your question'"
echo "4. Interactive mode: python main.py interactive"
echo ""
echo "Or try the Jupyter notebook: jupyter notebook notebooks/multimodal_rag_demo.ipynb"
echo ""
