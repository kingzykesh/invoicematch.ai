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

# Load environment variables from .env file
load_dotenv()

# Configure logging to show timestamps and log levels
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="InvoiceMatch.AI API",
    description="Backend for auto-reconciliation of hospital invoices and insurer payouts.",
    version="0.1.0"
)

# --- CORS Middleware ---
# Allows your frontend (running on a different domain) to communicate with this backend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, you might restrict this to your frontend's domain
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)


# --- API Client Setup ---

# OpenAI Client
try:
    openai_client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    logger.info("OpenAI client initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize OpenAI client: {e}")
    openai_client = None


# Curacel Client with dynamic environment handling
CURACEL_URLS = {
    "development": "https://api.avengers.claims.curacel.co",  # Test URL
    "production": "https://api.health.curacel.co"             # Production URL
}
APP_ENV = os.getenv("APP_ENV", "development").lower()
CURACEL_API_BASE_URL = CURACEL_URLS.get(APP_ENV)

if not CURACEL_API_BASE_URL:
    logger.warning(f"Invalid APP_ENV '{APP_ENV}'. Defaulting to development URL.")
    CURACEL_API_BASE_URL = CURACEL_URLS["development"]

logger.info(f"Application running in '{APP_ENV}' mode. Using Curacel API: {CURACEL_API_BASE_URL}")

CURACEL_API_KEY = os.getenv("CURACEL_API_KEY")
curacel_client = None
if CURACEL_API_KEY:
    curacel_client = httpx.AsyncClient(
        base_url=CURACEL_API_BASE_URL,
        headers={
            "Authorization": f"Bearer {CURACEL_API_KEY}",
            "Content-Type": "application/json"
        }
    )
else:
    logger.warning("Curacel client not initialized: CURACEL_API_KEY is not set in .env file.")


# --- The Magic: The AI Prompt ---
# This prompt is the most critical piece of the AI engine.
# It instructs the LLM on its role, the task, and the EXACT JSON format to return.
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
    """Extracts text from the bytes of a PDF file."""
    text = ""
    try:
        # Use io.BytesIO to treat the byte string as a file
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        logger.error(f"Failed to extract text from PDF: {e}")
        raise ValueError("Could not process the PDF file. It might be corrupted or not a valid PDF.")
    return text


async def log_claim_to_curacel(reconciliation_data: Dict[str, Any], summary: str) -> str:
    """
    Logs a discrepancy to Curacel by creating a new claim.
    Returns a status message for the frontend.
    """
    if not curacel_client:
        msg = "Curacel integration is not configured on the server."
        logger.warning(msg)
        return msg

    try:
        discrepancy_amount = reconciliation_data.get("discrepancyAmount", 0)
        ai_line_items = reconciliation_data.get("lineItems", [])
        
        curacel_items = []
        for item in ai_line_items:
            # We only want to include underpaid or denied items in the new claim
            if item.get("status") != "Paid in Full":
                curacel_items.append({
                    "service_type": "SERVICE",  # Generic type as we can't infer this from text
                    "name": item.get("description", "N/A"),
                    "quantity": 1,              # Assumption for the demo
                    "unit_price": item.get("billed", 0),
                    "total_price": item.get("billed", 0)
                })
        
        # If there are no items with issues, no need to create a claim
        if not curacel_items:
            return "Discrepancy noted, but no specific line items were flagged for claim creation."

        # Build the final payload for the Curacel API
        # Using placeholder IDs as per our hackathon strategy.
        payload = {
            "claim_type": "PRIMARY",
            "provider_id": 1,  # Placeholder
            "enrollee_id": 1,  # Placeholder
            "date_of_service": datetime.now().strftime("%Y-%m-%d"),
            "amount_claimed": discrepancy_amount,
            "items": curacel_items,
            "notes": f"Automated Claim from InvoiceMatch.AI: {summary}"
        }

        logger.info(f"Sending claim to Curacel: {json.dumps(payload)}")
        response = await curacel_client.post("/api/v1/claims", json=payload)
        response.raise_for_status()  # Raises HTTPError for 4xx/5xx responses

        claim_id = response.json().get("data", {}).get("id", "N/A")
        success_msg = f"Successfully logged discrepancy to Curacel. Claim ID: {claim_id}"
        logger.info(success_msg)
        return success_msg

    except httpx.RequestError as e:
        error_msg = f"Failed to connect to Curacel API: {e}"
        logger.error(error_msg)
        return error_msg
    except httpx.HTTPStatusError as e:
        error_msg = f"Curacel API Error: {e.response.status_code} - {e.response.text}"
        logger.error(error_msg)
        return error_msg
    except Exception as e:
        error_msg = f"An unexpected error occurred during Curacel logging: {e}"
        logger.error(error_msg)
        return error_msg


# --- API Endpoints ---

@app.get("/", include_in_schema=False)
async def root():
    """Root endpoint for health checks."""
    return {"message": "InvoiceMatch.AI Backend is running!"}


@app.post("/reconcile")
async def reconcile_documents(
    invoice_file: UploadFile = File(..., description="The hospital's submitted invoice (PDF)"),
    payout_summary_file: UploadFile = File(..., description="The insurer's payout summary (PDF)")
):
    """
    Accepts two PDF files, extracts their text, uses an LLM to compare them,
    and returns a structured JSON reconciliation report. If a discrepancy is found,
    it attempts to log a claim to the Curacel API.
    """
    if not openai_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenAI client is not configured on the server. Please check API key."
        )

    logger.info("Received reconciliation request. Reading and processing files.")
    try:
        invoice_content_bytes = await invoice_file.read()
        payout_content_bytes = await payout_summary_file.read()
        invoice_text = extract_text_from_pdf(invoice_content_bytes)
        payout_text = extract_text_from_pdf(payout_content_bytes)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"An unexpected error occurred during file processing: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An error occurred while processing files.")

    full_prompt = PROMPT_TEMPLATE.format(invoice_text=invoice_text, payout_text=payout_text)

    try:
        logger.info("Sending request to OpenAI API...")
        chat_completion = await openai_client.chat.completions.create(
            messages=[{"role": "user", "content": full_prompt}],
            model="gpt-4-turbo-preview",
            response_format={"type": "json_object"},
            temperature=0.1,  # Low temperature for deterministic, structured output
        )
        response_content = chat_completion.choices[0].message.content
        logger.info("Received successful response from OpenAI API.")

        parsed_data = json.loads(response_content)
        
        # Stretch Goal: Curacel integration
        curacel_status = "Not required: No discrepancy found."
        reconciliation_details = parsed_data.get("reconciliation", {})
        if reconciliation_details and reconciliation_details.get("discrepancyAmount", 0) > 0:
            logger.info("Discrepancy detected. Attempting to log claim to Curacel.")
            curacel_status = await log_claim_to_curacel(
                reconciliation_details, 
                parsed_data.get("executiveSummary", "")
            )
        
        final_response = {
            "status": "success",
            "data": parsed_data,
            "curacel_integration_status": curacel_status
        }
        return final_response

    except openai.APIError as e:
        logger.error(f"OpenAI API Error: {e}")
        raise HTTPException(status_code=502, detail=f"An error occurred with the AI provider: {e}")
    except json.JSONDecodeError:
        logger.error(f"Failed to parse JSON from OpenAI response: {response_content}")
        raise HTTPException(status_code=500, detail="The AI returned an invalid format. Please try again.")
    except Exception as e:
        logger.error(f"An unexpected error occurred during AI processing: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected server error occurred: {e}")