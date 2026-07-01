import os
from groq import Groq
from deepeval.models import DeepEvalBaseLLM


class GroqDeepEvalLLM(DeepEvalBaseLLM):
    def __init__(self, model_name=None):
        self.model_name = model_name or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    def load_model(self):
        return self.client

    def generate(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {
                    "role": "system",
                    "content": "You are a strict evaluator. Return concise, valid evaluation output."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0,
        )

        return response.choices[0].message.content

    async def a_generate(self, prompt: str) -> str:
        return self.generate(prompt)

    def get_model_name(self):
        return f"Groq {self.model_name}"