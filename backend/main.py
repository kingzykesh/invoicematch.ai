import os
import json
import logging
from dotenv import load_dotenv

import openai
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


# --- API Endpoint ---

@app.post("/reconcile")
async def reconcile_documents(
    invoice_file: UploadFile = File(..., description="The hospital's submitted invoice (PDF, TXT, etc.)"),
    payout_summary_file: UploadFile = File(..., description="The insurer's payout summary document.")
):
    """
    Accepts an invoice and a payout summary, compares them using an LLM,
    and returns a structured JSON reconciliation report.
    """
    if not client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenAI client is not configured. Check API key."
        )

    logger.info("Received reconciliation request.")

    try:
        # 1. Read the content of the uploaded files
        invoice_content = await invoice_file.read()
        payout_content = await payout_summary_file.read()

        # For this MVP, we assume the files are text-based. In a real app,
        # you would use a library like PyPDF2 or pdfplumber to extract text from PDFs.
        # For the hackathon, you can use mock .txt files.
        invoice_text = invoice_content.decode('utf-8')
        payout_text = payout_content.decode('utf-8')
        logger.info("Successfully read and decoded both files.")

    except Exception as e:
        logger.error(f"Error reading uploaded files: {e}")
        raise HTTPException(status_code=400, detail=f"Error processing files: {e}")

    # 2. Format the prompt with the document text
    full_prompt = PROMPT_TEMPLATE.format(invoice_text=invoice_text, payout_text=payout_text)

    try:
        logger.info("Sending request to OpenAI API...")
        # 3. Call the OpenAI API
        chat_completion = await client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": full_prompt,
                }
            ],
            model="gpt-4-turbo-preview",  # GPT-4 is better for complex structured data tasks
            # model="gpt-3.5-turbo-0125", # A cheaper, faster alternative if needed
            response_format={"type": "json_object"}, # This is the magic!
            temperature=0.1, # Low temperature for more deterministic, factual output
        )

        response_content = chat_completion.choices[0].message.content
        logger.info("Received successful response from OpenAI API.")

        # 4. Parse the JSON response from the LLM
        parsed_data = json.loads(response_content)

        # 5. Return the data in the agreed-upon API contract format
        # The structure from the LLM already matches our contract, so we just wrap it.
        return {
            "status": "success",
            "data": parsed_data
        }

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