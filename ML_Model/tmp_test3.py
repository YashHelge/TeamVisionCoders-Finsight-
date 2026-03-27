import sys
import os
import asyncio
import json
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pipeline.llm_extractor import batch_extract_llm

async def main():
    messages = [
        "A/C X8928 Debit Rs.100.00 for UPI to kavilpad muthu on 19-03-26 Ref 607899062170.",
        "Your a/c no. XXXXXX1234 is credited by Rs. 1000.00 on 20-03-26 by A/c linked to mobile 9876543210 (UPI Ref no 1234567890).",
        "Dear Customer, Payment of Rs. 495.00 credited to your Acc No. XXXXX156406 on 27/03/26-SBI"
    ]
    res = await batch_extract_llm(messages)
    print(json.dumps(res, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
