# evaluation/gemini_deepeval_model.py

import os
import google.generativeai as genai
from deepeval.models import DeepEvalBaseLLM


class GeminiDeepEvalLLM(DeepEvalBaseLLM):
    def __init__(self):
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        self.model = genai.GenerativeModel("gemini-2.5-flash")

    def load_model(self):
        return self.model

    def generate(self, prompt: str):
        response = self.model.generate_content(prompt)
        return response.text

    async def a_generate(self, prompt):
        return self.generate(prompt)

    def get_model_name(self):
        return "Gemini 2.5 Flash"