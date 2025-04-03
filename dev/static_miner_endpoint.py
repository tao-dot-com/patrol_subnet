from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional, Dict
import ast
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

with open('example_payload.txt', 'r') as file:
    content = file.read()

# Safely evaluate the string as a Python literal (like a dictionary)
test_subgraph_output = ast.literal_eval(content)

# Define the data class using Pydantic's BaseModel
class PatrolSynapse(BaseModel):
    target: Optional[str] = None
    subgraph_output: Optional[Dict] = None

app = FastAPI()

@app.post("/PatrolSynapse")
async def handle_patrol_synapse(patrol: PatrolSynapse):
    # Log the incoming request
    logger.info(f"Received request with payload: {patrol.model_dump_json()}")
    
    patrol.subgraph_output = test_subgraph_output
    return patrol