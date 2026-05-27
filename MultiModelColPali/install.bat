@echo off
echo === Step 1: PyTorch CPU ===
pip install torch==2.5.1 torchvision --index-url https://download.pytorch.org/whl/cpu --timeout 600
echo PyTorch exit code: %ERRORLEVEL%

echo.
echo === Step 2: All other packages ===
pip install colpali-engine>=0.3.4 transformers>=4.44.0 peft>=0.11.0 lancedb>=0.13.0 pyarrow>=14.0.0 pymupdf>=1.24.0 anthropic>=0.40.0 streamlit>=1.38.0 python-dotenv>=1.0.0 pillow>=10.0.0 numpy>=1.26.0 tqdm>=4.66.0 --timeout 300
echo Packages exit code: %ERRORLEVEL%

echo.
echo === Verification ===
python -c "import torch, colpali_engine, lancedb, anthropic, streamlit; print('ALL PACKAGES OK')"
echo Done.
