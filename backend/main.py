import os
import json
import logging
from dotenv import load_dotenv
import io

import openai
import pdfplumber
from fastapi import FastAPI, File, UploadFile, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

# --- Configuration & Setup ---

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="InvoiceMatch.AI API",
    description="Backend for auto-reconciliation of hospital invoices and insurer payouts.",
    version="0.1.0"
)

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)


# --- OpenAI API Client Setup ---
try:
    client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    logger.info("OpenAI client initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize OpenAI client: {e}")
    client = None


# --- The Magic: The AI Prompt ---
# This prompt is the most critical piece of the AI engine.
# It instructs the LLM on its role, the task, and the EXACT JSON format to return.
# Using GPT-4's `response_format={"type": "json_object"}` feature makes this very reliable.

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
{
  "executiveSummary": "A natural language summary here...",
  "reconciliation": {
    "totalBilled": 50000,
    "totalPaid": 42500,
    "discrepancyAmount": 7500,
    "lineItems": [
      {"description": "Item Name", "billed": 15000, "paid": 15000, "status": "Paid in Full"},
      {"description": "Another Item", "billed": 5000, "paid": 4250, "status": "Underpaid"},
      {"description": "A Third Item", "billed": 7500, "paid": 0, "status": "Denied"}
    ]
  }
}

Here are the documents:

--- HOSPITAL INVOICE TEXT ---
{invoice_text}
--- END HOSPITAL INVOICE TEXT ---


--- INSURER PAYOUT SUMMARY TEXT ---
{payout_text}
--- END INSURER PAYOUT SUMMARY TEXT ---

Now, generate the JSON response.
"""


# --- Helper function to extract text from a PDF ---
def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Extracts text from the bytes of a PDF file.
    """
    text = ""
    # Use io.BytesIO to treat the byte string as a file
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            # Extract text from each page and add it to the string.
            # Use `or ""` to handle pages with no text.
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text

# --- API Endpoint ---

@app.post("/reconcile")
async def reconcile_documents(
    invoice_file: UploadFile = File(..., description="The hospital's submitted invoice (PDF)"),
    payout_summary_file: UploadFile = File(..., description="The insurer's payout summary (PDF)")
):
    if not client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenAI client is not configured. Check API key."
        )

    logger.info("Received reconciliation request. Reading files.")

    try:
        # 1. Read the raw bytes of the uploaded files
        invoice_content_bytes = await invoice_file.read()
        payout_content_bytes = await payout_summary_file.read()

        # 2. Extract text from the PDF bytes using our new helper function
        #    This replaces the old `.decode('utf-8')` line
        invoice_text = extract_text_from_pdf(invoice_content_bytes)
        payout_text = extract_text_from_pdf(payout_content_bytes)
        
        logger.info("Successfully extracted text from both PDF files.")

    except Exception as e:
        logger.error(f"Error processing files: {e}")
        # Make the error message more user-friendly
        raise HTTPException(status_code=400, detail=f"Error processing files: {e}. Please ensure you are uploading valid PDF documents.")

    full_prompt = PROMPT_TEMPLATE.format(invoice_text=invoice_text, payout_text=payout_text)

    try:
        logger.info("Sending request to OpenAI API...")
        chat_completion = await client.chat.completions.create(
            messages=[{"role": "user", "content": full_prompt}],
            model="gpt-4-turbo-preview",
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        response_content = chat_completion.choices[0].message.content
        logger.info("Received successful response from OpenAI API.")

        parsed_data = json.loads(response_content)
        return {"status": "success", "data": parsed_data}

    except openai.APIError as e:
        logger.error(f"OpenAI API Error: {e}")
        raise HTTPException(status_code=500, detail=f"An error occurred with the OpenAI API: {e}")
    except json.JSONDecodeError:
        logger.error("Failed to parse JSON from OpenAI response.")
        raise HTTPException(status_code=500, detail="The AI returned an invalid format. Please try again.")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected server error occurred: {e}")
@app.get("/", include_in_schema=False)
async def root():
    return {"message": "InvoiceMatch.AI Backend is running!"}