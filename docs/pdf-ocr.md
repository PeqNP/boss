# PDF OCR

The xAI tool does not understand how to read binary PDFs. Therefore, it is necessary to convert the HIGuidlines.pdf into a Markdown document. To do that, do the following:

```
cd ~
source ~/.venv/bin/activate
pip3 install marker-pdf
export TORCH_DEVICE=mps
marker_single ~/source/boss/docs/HIGuidelines.pdf
```
