# PDF OCR

The xAI tool reads text, so convert `HIGuidelines.pdf` into a Markdown document first:

```
cd ~
source ~/.venv/bin/activate
pip3 install marker-pdf
export TORCH_DEVICE=mps
marker_single ~/source/boss/docs/HIGuidelines.pdf
```
