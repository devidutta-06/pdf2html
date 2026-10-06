# PDF to HTML Converter

A tool that converts single-page PDF files to semantic, responsive HTML using layout information and local LLM refinement.

## Overview

This tool takes a PDF file and converts it into responsive HTML through multiple steps:
1. Extract PDF content (text, shapes, images) 
2. Convert to Layout-LaTeX (LLX) format
3. Generate golden HTML with absolute positioning
4. Refine using a local Ollama LLM for semantic, responsive markup

## Features

- Converts single-page PDFs to HTML
- Preserves layout and styling information
- Uses local Ollama model for semantic refinement
- Generates responsive HTML with CSS Grid/Flexbox
- No external dependencies beyond Python libraries
- Maintains original text content and structure

## Requirements

- Python 3.12+
- pymupdf (fitz)
- ollama
- python-dotenv

Install requirements with:
```bash
pip install -r requirements.txt
```

## Usage

```bash
python main.py <path_to_pdf> [--no-llm] [--out output_folder]
```

### Options:
- `--no-llm`: Skip the Ollama refinement step (outputs golden.html only)
- `--out`: Specify output folder (default: 'out')

## Output Files

The tool generates three files in the output directory:
1. `layout.llx` - The intermediate layout representation
2. `golden.html` - HTML with absolute positioning and basic styling  
3. `output.html` - Refined HTML with semantic elements and responsive design (if LLM enabled)

## Environment Variables

Create a `.env` file with:
```
OLLAMA_HOST= ollama_url
MODEL=model_name
NUM_CTX=16384
```

## How It Works

1. **PDF Extraction** (`extract.py`): Uses PyMuPDF to extract text, shapes, and images from the PDF
2. **LLX Conversion** (`llx.py`): Converts elements to Layout-LaTeX format for structured layout representation
3. **Golden HTML Generation** (`plot.py`): Creates absolute-positioned HTML with CSS styles
4. **LLM Refinement** (`llm.py`): Uses Ollama to convert golden HTML to semantic, responsive HTML

## Example

```bash
python main.py sample.pdf
```

This will create an `out/` directory containing the three output files.

# Issues
- Need to Handel Image blocks inside the image PDF
- Need to improve prompt 
- It Only work with Image PRFs


## License

MIT