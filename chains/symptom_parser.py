from typing import List

from pydantic import BaseModel

from langchain import LLMChain, PromptTemplate
from langchain.output_parsers import PydanticOutputParser

from langchain_gemini import GeminiLLM


class SymptomResult(BaseModel):
    probable_conditions: List[str]
    recommendations: List[str]
    disclaimer: str


def make_parser_chain(api_key: str = None) -> LLMChain:
    llm = GeminiLLM(api_key=api_key)

    parser = PydanticOutputParser(pydantic_object=SymptomResult)

    prompt_template = (
        "You are a helpful medical-educational assistant.\n"
        "Given the following user symptoms, list probable_conditions (as a list of short condition names), "
        "recommended next steps (as a list), and include a clear educational disclaimer.\n\n"
        "Symptom text:\n{symptoms}\n\n"
        "Return ONLY valid JSON parsable to the following schema:\n"
        + parser.get_format_instructions()
    )

    prompt = PromptTemplate(input_variables=["symptoms"], template=prompt_template)

    chain = LLMChain(llm=llm, prompt=prompt, output_key="result")
    # wrap the chain output with the parser externally when calling
    chain.parser = parser
    return chain


def run_parser(chain: LLMChain, symptoms: str):
    raw = chain.run(symptoms=symptoms)
    # parse using the PydanticOutputParser attached
    parsed = chain.parser.parse(raw)
    return parsed
