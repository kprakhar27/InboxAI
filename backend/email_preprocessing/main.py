import os
import sys

from dotenv import load_dotenv

load_dotenv("/Users/pradnyeshchoudhari/IE 7374 - LOCAL/InboxAI/backend/.env")

# Add the project directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

email = "learningg951@gmail.com"
from pipelines.preprocessing_pipeline import PreprocessingPipeline

pipeline = PreprocessingPipeline(email)
pipeline.process_ready_items()
