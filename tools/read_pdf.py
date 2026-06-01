import os
import csv
import json
import zipfile
import xml.etree.ElementTree as ET
import pypdf
from typing import Optional
from tools.registry import registry, BaseTool
from brain.llm import llm_client
from config.logging import logger

def read_docx_native(file_path: str) -> str:
    """Extracts text from a .docx file natively using standard zipfile and xml parsing."""
    try:
        with zipfile.ZipFile(file_path) as docx:
            xml_content = docx.read('word/document.xml')
            root = ET.fromstring(xml_content)
            
            # The OpenXML namespace for wordprocessingml
            ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            
            paragraphs = []
            for p in root.findall('.//w:p', ns):
                text_runs = []
                for t in p.findall('.//w:t', ns):
                    if t.text:
                        text_runs.append(t.text)
                if text_runs:
                    paragraphs.append("".join(text_runs))
            return "\n".join(paragraphs)
    except Exception as e:
        raise Exception(f"Failed to parse .docx file natively: {e}")

def extract_text_from_file(file_path: str, start_page: Optional[int] = None, end_page: Optional[int] = None, max_lines: Optional[int] = None) -> str:
    """Helper to extract text from PDF, DOCX, TXT, MD, LOG, CSV, JSON files."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: '{file_path}'")
        
    ext = os.path.splitext(file_path)[1].lower()
    
    # 1. Parse PDF
    if ext == '.pdf':
        try:
            reader = pypdf.PdfReader(file_path)
            total_pages = len(reader.pages)
            
            # Calculate range
            sp = max(1, start_page) if start_page is not None else 1
            ep = min(total_pages, end_page) if end_page is not None else total_pages
            
            if sp > ep:
                return f"Invalid page range: {sp}-{ep} (Total pages: {total_pages})"
                
            text_pages = []
            for page_num in range(sp - 1, ep):
                page_text = reader.pages[page_num].extract_text()
                if page_text:
                    text_pages.append(f"--- Page {page_num + 1} ---\n{page_text}")
                    
            if not text_pages:
                return "The PDF contains no readable text (it may be scanned or empty)."
            return "\n\n".join(text_pages)
        except Exception as e:
            raise Exception(f"Failed to read PDF file: {e}")
            
    # 2. Parse DOCX
    elif ext == '.docx':
        return read_docx_native(file_path)
        
    # 3. Parse CSV
    elif ext == '.csv':
        try:
            rows = []
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                reader = csv.reader(f)
                for idx, row in enumerate(reader):
                    if max_lines is not None and idx >= max_lines:
                        rows.append(f"... [Truncated: displayed first {max_lines} rows] ...")
                        break
                    rows.append(", ".join(row))
            return "\n".join(rows)
        except Exception as e:
            raise Exception(f"Failed to read CSV file: {e}")
            
    # 4. Parse JSON
    elif ext == '.json':
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                data = json.load(f)
            formatted_json = json.dumps(data, indent=2)
            if max_lines is not None:
                lines = formatted_json.split("\n")
                if len(lines) > max_lines:
                    return "\n".join(lines[:max_lines]) + f"\n... [Truncated: displayed first {max_lines} lines] ..."
            return formatted_json
        except Exception as e:
            raise Exception(f"Failed to read JSON file: {e}")
            
    # 5. Parse standard Text-based files
    else:
        # We read text/md/py/log/java etc.
        try:
            lines = []
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                for idx, line in enumerate(f):
                    if max_lines is not None and idx >= max_lines:
                        lines.append(f"... [Truncated: displayed first {max_lines} lines] ...")
                        break
                    lines.append(line.rstrip())
            return "\n".join(lines)
        except Exception as e:
            raise Exception(f"Failed to read text file: {e}")

@registry.register(
    name="read_file",
    description="Reads and extracts text from a local file (supports PDF, DOCX, TXT, LOG, MD, PY, JAVA, JSON, CSV).",
    args_schema={
        "file_path": {
            "type": "string",
            "description": "Absolute path to the file to read."
        },
        "start_page": {
            "type": "integer",
            "description": "Page number to start reading from (1-indexed, PDF only)."
        },
        "end_page": {
            "type": "integer",
            "description": "Page number to stop reading at (PDF only)."
        },
        "max_lines": {
            "type": "integer",
            "description": "Maximum number of lines to display (text/data files only)."
        }
    },
    risk_level="low"
)
class ReadFileTool(BaseTool):
    def execute(self, file_path: str, start_page: Optional[int] = None, end_page: Optional[int] = None, max_lines: Optional[int] = None) -> dict:
        logger.info(f"Executing read_file on: '{file_path}'")
        try:
            text = extract_text_from_file(file_path, start_page, end_page, max_lines)
            return {"success": True, "output": text}
        except Exception as e:
            msg = f"Error reading file '{file_path}': {e}"
            logger.error(msg)
            return {"success": False, "output": msg}

def summarize_text_via_llm(text: str, focus_area: Optional[str] = None) -> str:
    """Performs chunked map-reduce summarization if text is large, or direct single-pass summary if small."""
    words = text.split()
    word_count = len(words)
    
    # Threshold for chunking: 2000 words
    if word_count <= 2000:
        logger.info(f"Text length ({word_count} words) is within limits. Running single-pass summary.")
        prompt = (
            "You are a helpful, precise executive assistant. Please provide a clear, structured summary of the following text "
            "formatted in beautiful Markdown.\n"
            "Use clear sections: '## Executive Summary', '## Key Findings', and '## Action Items/Takeaways' where appropriate.\n"
        )
        if focus_area:
            prompt += f"Ensure the summary places special emphasis and focus on the following area: '{focus_area}'.\n"
        prompt += f"\n--- Text ---\n{text}\n"
        
        messages = [{"role": "user", "content": prompt}]
        return llm_client.chat(messages, stream=False)
        
    # Large file: Map-Reduce Chunking Summarization
    logger.info(f"Text length ({word_count} words) exceeds threshold. Starting Map-Reduce chunking pipeline.")
    
    # 1. Map Phase: Split into chunks of 1500 words with 200 words overlap
    chunk_size = 1500
    overlap = 200
    chunks = []
    
    i = 0
    while i < word_count:
        chunk_words = words[i : i + chunk_size]
        chunks.append(" ".join(chunk_words))
        i += chunk_size - overlap
        
    logger.debug(f"Split text into {len(chunks)} chunks for individual summarization.")
    
    intermediate_summaries = []
    for idx, chunk in enumerate(chunks, 1):
        logger.debug(f"Summarizing chunk {idx}/{len(chunks)}...")
        chunk_prompt = (
            f"Summarize the following section of a larger document. Extract all important details, "
            f"facts, and statistics. Keep the summary concise but highly informative.\n"
        )
        if focus_area:
            chunk_prompt += f"Focus your summary especially on this area: '{focus_area}'.\n"
        chunk_prompt += f"\n--- Section Content ---\n{chunk}\n"
        
        messages = [{"role": "user", "content": chunk_prompt}]
        chunk_summary = llm_client.chat(messages, stream=False)
        intermediate_summaries.append(f"--- Section {idx} Summary ---\n{chunk_summary}")
        
    # 2. Reduce Phase: Consolidate intermediate summaries
    logger.info("Map phase complete. Beginning Reduce phase to consolidate summaries.")
    combined_summaries = "\n\n".join(intermediate_summaries)
    
    reduce_prompt = (
        "You are an expert executive assistant. You are given a set of intermediate section summaries extracted from a very "
        "large document. Please combine and synthesize these summaries into a single, cohesive, beautifully structured "
        "global summary formatted in Markdown.\n\n"
        "Your final output MUST follow this exact structure:\n"
        "# Document Executive Summary\n"
        "Provide a high-level overview of the entire document.\n\n"
        "## Key Discoveries & Findings\n"
        "List the most critical facts, numbers, dates, or discoveries from all sections as clean bullet points.\n\n"
        "## Core Conclusions / Action Items\n"
        "Summarize the main takeaways, takeaways, and next steps.\n\n"
    )
    if focus_area:
        reduce_prompt += f"IMPORTANT: This summary must place strong focus and emphasis on: '{focus_area}'.\n\n"
    reduce_prompt += f"--- Intermediate Summaries ---\n{combined_summaries}\n"
    
    messages = [{"role": "user", "content": reduce_prompt}]
    return llm_client.chat(messages, stream=False)

@registry.register(
    name="summarize_file",
    description="Generates a structured, beautiful Markdown summary of a local file (supports PDF, DOCX, TXT, LOG, MD, PY, JAVA, JSON, CSV).",
    args_schema={
        "file_path": {
            "type": "string",
            "description": "Absolute path to the file to summarize."
        },
        "focus_area": {
            "type": "string",
            "description": "An optional topic or perspective to focus the summary on (e.g., 'action items', 'financial figures', 'errors')."
        },
        "start_page": {
            "type": "integer",
            "description": "Page number to start reading from (1-indexed, PDF only)."
        },
        "end_page": {
            "type": "integer",
            "description": "Page number to stop reading at (PDF only)."
        }
    },
    risk_level="low"
)
class SummarizeFileTool(BaseTool):
    def execute(self, file_path: str, focus_area: Optional[str] = None, start_page: Optional[int] = None, end_page: Optional[int] = None) -> dict:
        logger.info(f"Executing summarize_file on: '{file_path}' (focus: '{focus_area}')")
        try:
            # Step 1: Extract text (read the whole range)
            text = extract_text_from_file(file_path, start_page, end_page)
            
            # Step 2: Summarize text
            summary = summarize_text_via_llm(text, focus_area)
            return {"success": True, "output": summary}
        except Exception as e:
            msg = f"Error summarizing file '{file_path}': {e}"
            logger.error(msg)
            return {"success": False, "output": msg}
