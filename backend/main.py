import os
import json
import logging
import io
from typing import Dict, Any
from datetime import datetime
from dotenv import load_dotenv

import openai
import pdfplumber
import httpx
from fastapi import FastAPI, File, UploadFile, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

# --- Configuration & Setup ---
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
app = FastAPI(title="InvoiceMatch.AI API", description="Backend for auto-reconciliation.", version="0.1.0")

# --- CORS Middleware ---
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- API Client Setup ---
# OpenAI Client
try:
    openai_client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    logger.info("OpenAI client initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize OpenAI client: {e}")
    openai_client = None

# Simplified Curacel Client Setup
CURACEL_API_BASE_URL = os.getenv("CURACEL_API_BASE_URL")
CURACEL_API_KEY = os.getenv("CURACEL_API_KEY")
curacel_client = None

if CURACEL_API_BASE_URL and CURACEL_API_KEY:
    logger.info(f"Using Curacel API Endpoint: {CURACEL_API_BASE_URL}")
    curacel_client = httpx.AsyncClient(
        base_url=CURACEL_API_BASE_URL,
        headers={"Authorization": f"Bearer {CURACEL_API_KEY}", "Content-Type": "application/json"}
    )
else:
    logger.warning("Curacel client not initialized: Check CURACEL_API_BASE_URL and CURACEL_API_KEY.")

# --- The AI Prompt (Unchanged) ---
PROMPT_TEMPLATE = """
You are an expert AI assistant for hospital financial reconciliation. Your task is to compare a hospital's submitted invoice with an insurer's payout summary. You must identify discrepancies and provide a clear, structured summary.
**IMPORTANT INSTRUCTIONS:**
1.  Analyze the two documents provided: a Hospital Invoice and an Insurer Payout Summary.
2.  Match line items between the two documents based on their description.
3.  Calculate the total amount billed by the hospital and the total amount paid by the insurer.
4.  Identify any difference between the billed and paid amounts for each line item and for the total.
5.  Generate a concise, professional executive summary for a hospital finance team, explaining the overall result.
6.  You MUST return your findings in a single, valid JSON object. Do not include any text, explanations, or markdown formatting like ```json before or after the JSON object.
The JSON object must follow this exact structure:
{{
  "executiveSummary": "A natural language summary here...",
  "reconciliation": {{
    "totalBilled": 50000,
    "totalPaid": 42500,
    "discrepancyAmount": 7500,
    "lineItems": [
      {{"description": "Consultation Fee", "billed": 15000, "paid": 15000, "status": "Paid in Full"}},
      {{"description": "IV Fluids", "billed": 5000, "paid": 4250, "status": "Underpaid"}},
      {{"description": "Lab Test XYZ", "billed": 7500, "paid": 0, "status": "Denied"}}
    ]
  }}
}}
Here are the documents:
--- HOSPITAL INVOICE TEXT ---
{invoice_text}
--- END HOSPITAL INVOICE TEXT ---
--- INSURER PAYOUT SUMMARY TEXT ---
{payout_text}
--- END INSURER PAYOUT SUMMARY TEXT ---
Now, generate the JSON response.
"""

# --- Helper Functions ---
def extract_text_from_pdf(file_bytes: bytes) -> str:
    text = ""
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text: text += page_text + "\n"
    except Exception as e:
        logger.error(f"Failed to extract text from PDF: {e}")
        raise ValueError("Could not process the PDF file.")
    return text

# <<< FINAL CORRECTED FUNCTION >>>
async def log_claim_to_curacel(reconciliation_data: Dict[str, Any], summary: str) -> str:
    if not curacel_client:
        return "Curacel integration is not configured on the server."
    try:
        discrepancy_amount = reconciliation_data.get("discrepancyAmount", 0)
        ai_line_items = reconciliation_data.get("lineItems", [])
        curacel_items = []
        for item in ai_line_items:
            if item.get("status") != "Paid in Full":
                curacel_items.append({
                    "description": item.get("description", "N/A"),
                    "qty": 1,
                    "unit_price_billed": item.get("billed", 0),
                    "service_type": "SERVICE", 
                })
        if not curacel_items:
            return "Discrepancy noted, but no specific line items were flagged for claim creation."
            
        payload = {
            "provider_id": 234112,
            "amount_claimed": discrepancy_amount,
            "claim_type": "PRIMARY",
            "encounter_date": datetime.now().strftime("%Y-%m-%d"),
            "enrollee": {
                "insurance_no": "PLACEHOLDER-INS-12345",
                "first_name": "John",    
                "last_name": "Doe"       
            },
            "diagnoses": {               
                "icd_codes": ["Z00.0"],
                "names": ["General medical examination"],
                "ids": [1]
            },
            "items": curacel_items,
            "notes": f"Automated Claim from InvoiceMatch.AI: {summary}"
        }

        logger.info(f"Sending final compliant payload to Curacel: {json.dumps(payload)}")
        response = await curacel_client.post("/api/v1/claims", json=payload)
        response.raise_for_status()
        claim_id = response.json().get("data", {}).get("id", "N/A")
        return f"Successfully logged discrepancy to Curacel. Claim ID: {claim_id}"
    except httpx.RequestError as e: return f"Failed to connect to Curacel API: {e}"
    except httpx.HTTPStatusError as e: return f"Curacel API Error: {e.response.status_code} - {e.response.text}"
    except Exception as e: return f"An unexpected error occurred during Curacel logging: {e}"

# --- API Endpoints ---
@app.get("/", include_in_schema=False)
async def root():
    return {"message": "InvoiceMatch.AI Backend is running!"}

@app.post("/reconcile")
async def reconcile_documents(invoice_file: UploadFile = File(...), payout_summary_file: UploadFile = File(...)):
    if not openai_client: raise HTTPException(status_code=503, detail="OpenAI client is not configured.")
    try:
        invoice_text = extract_text_from_pdf(await invoice_file.read())
        payout_text = extract_text_from_pdf(await payout_summary_file.read())
    except ValueError as e: raise HTTPException(status_code=400, detail=str(e))
    try:
        chat_completion = await openai_client.chat.completions.create(
            messages=[{"role": "user", "content": PROMPT_TEMPLATE.format(invoice_text=invoice_text, payout_text=payout_text)}],
            model="gpt-4-turbo-preview", response_format={"type": "json_object"}, temperature=0.1
        )
        parsed_data = json.loads(chat_completion.choices[0].message.content)
        curacel_status = "Not required: No discrepancy found."
        reconciliation_details = parsed_data.get("reconciliation", {})
        if reconciliation_details and reconciliation_details.get("discrepancyAmount", 0) > 0:
            curacel_status = await log_claim_to_curacel(reconciliation_details, parsed_data.get("executiveSummary", ""))
        return {"status": "success", "data": parsed_data, "curacel_integration_status": curacel_status}
    except openai.APIError as e: raise HTTPException(status_code=502, detail=f"AI provider error: {e}")
    except json.JSONDecodeError: raise HTTPException(status_code=500, detail="AI returned invalid format.")
    except Exception as e: raise HTTPException(status_code=500, detail=f"Unexpected server error: {e}")