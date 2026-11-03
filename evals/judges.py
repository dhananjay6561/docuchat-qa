"""Judge models for DeepEval and Ragas.

JUDGE_PROVIDER picks the judge:
  recorded  - replay judge responses from evals/cassettes/judge.jsonl (offline, deterministic)
  anthropic - a live Claude judge (needs ANTHROPIC_API_KEY)

Both libraries send the judge a text prompt and parse JSON from the reply, so recording at the
prompt level captures everything the judge decided.
"""

import os
from pathlib import Path
from typing import Any

from deepeval.models import DeepEvalBaseLLM
from langchain_core.outputs import Generation, LLMResult
from ragas.llms.base import BaseRagasLLM

from app.llm.cassette import Cassette

CASSETTE_DIR = Path(__file__).resolve().parent / "cassettes"
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "claude-opus-5-5")


def _prompt_text(prompt: Any) -> str:
    return prompt if isinstance(prompt, str) else str(prompt)


class RecordedDeepEvalJudge(DeepEvalBaseLLM):
    def __init__(self, cassette: Cassette) -> None:
        self.cassette = cassette
        super().__init__(model=f"recorded:{JUDGE_MODEL}")

    def load_model(self) -> "RecordedDeepEvalJudge":
        return self

    def generate(self, prompt: Any, schema: Any = None, **_: Any) -> str:
        # Returning the raw JSON text lets DeepEval parse it with its own (schema-aware) parser.
        return self.cassette.lookup({"judge": "deepeval", "prompt": _prompt_text(prompt)})

    async def a_generate(self, prompt: Any, schema: Any = None, **kwargs: Any) -> str:
        return self.generate(prompt, schema, **kwargs)

    def get_model_name(self) -> str:
        return f"recorded:{JUDGE_MODEL}"


class RecordedRagasJudge(BaseRagasLLM):
    def __init__(self, cassette: Cassette) -> None:
        super().__init__()
        self.cassette = cassette

    def generate_text(self, prompt: Any, n: int = 1, temperature: float = 0.01, stop=None, callbacks=None):
        text = self.cassette.lookup({"judge": "ragas", "prompt": prompt.to_string()})
        return LLMResult(generations=[[Generation(text=text)]])

    async def agenerate_text(self, prompt: Any, n: int = 1, temperature=0.01, stop=None, callbacks=None):
        return self.generate_text(prompt, n, temperature or 0.01, stop, callbacks)

    def is_finished(self, response: LLMResult) -> bool:
        return True

    async def generate(self, prompt: Any, n: int = 1, temperature=0.01, stop=None, callbacks=None):
        # Skip Ragas' retry wrapper: a cassette miss is not transient, retrying only adds delay.
        return self.generate_text(prompt, n, temperature or 0.01, stop, callbacks)


def judge_cassette() -> Cassette:
    return Cassette(CASSETTE_DIR / "judge.jsonl")


def build_deepeval_judge(cassette: Cassette) -> DeepEvalBaseLLM:
    if os.getenv("JUDGE_PROVIDER", "recorded") == "anthropic":
        from deepeval.models import AnthropicModel

        return AnthropicModel(model=JUDGE_MODEL)
    return RecordedDeepEvalJudge(cassette)


def build_ragas_judge(cassette: Cassette) -> BaseRagasLLM:
    if os.getenv("JUDGE_PROVIDER", "recorded") == "anthropic":
        from langchain_anthropic import ChatAnthropic  # optional extra, only for live judging
        from ragas.llms import LangchainLLMWrapper

        return LangchainLLMWrapper(ChatAnthropic(model=JUDGE_MODEL))
    return RecordedRagasJudge(cassette)
